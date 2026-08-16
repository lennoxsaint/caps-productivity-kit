from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


CAPABILITIES = load_script("capability_snapshot", "capability-snapshot.py")
ROUTING = load_script("verify_routing", "verify-routing.py")


def snapshot() -> dict:
    return CAPABILITIES.build_snapshot(
        {
            "snapshot_version": "1.0",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "codex-runtime-model-catalog",
            "models": [
                {
                    "id": "gpt-5.6-sol",
                    "provider": "openai",
                    "reasoning_levels": ["medium", "high", "max", "ultra"],
                    "live": True,
                    "entitled": True,
                    "allowed_by_policy": True,
                    "specialist_task_classes": [],
                },
                {
                    "id": "gpt-next-code",
                    "provider": "openai",
                    "reasoning_levels": ["low", "medium"],
                    "live": True,
                    "entitled": True,
                    "allowed_by_policy": True,
                    "specialist_task_classes": [],
                },
                {
                    "id": "daybreak-research",
                    "provider": "daybreak",
                    "reasoning_levels": ["high"],
                    "live": True,
                    "entitled": True,
                    "allowed_by_policy": True,
                    "specialist_task_classes": ["research_strategy"],
                },
            ],
        }
    )


def decision(capabilities: dict, **updates) -> dict:
    value = {
        "task_snapshot": {
            "objective": "Implement a bounded change.",
            "scope": ["Named files only."],
            "acceptance_criteria": ["Focused tests pass."],
            "risk_level": "low",
            "side_effects": "local_reversible",
            "evidence_refs": ["fixture"],
            "stop_conditions": ["Stop on scope expansion."],
        },
        "task_class": "coding",
        "requested_model": "gpt-next-code",
        "requested_thinking": "medium",
        "resolved_model": "gpt-next-code",
        "resolved_thinking": "medium",
        "capability_snapshot_digest": capabilities["digest"],
        "route_source": "selected",
        "routing_mode": "direct",
        "evidence_state": "runtime_observation",
        "execution_level": "worker",
        "worker_kind": "subagent",
        "fork_turns": "none",
        "delegation_depth": 1,
        "nested_delegation": False,
        "fanout": {
            "requested_workers": 1,
            "independent": True,
            "deterministic": True,
            "noncolliding": True,
        },
        "rationale": "The runtime advertises this bounded coding route.",
        "quality_gate": "Focused tests pass.",
        "escalate_when": ["The contract changes."],
        "authority": {
            "ceiling": "local_reversible",
            "allowed_actions": ["read", "analyze", "test", "local_reversible_edit"],
            "prohibited_actions": [
                "external_send", "production_write", "merge", "deploy", "publish",
                "credential_change", "irreversible_action", "authority_widening",
            ],
            "allowed": ["Edit named local files."],
            "prohibited": ["Deploy or publish."],
            "proof_required": ["Return test output."],
            "stop_conditions": ["Stop on scope expansion."],
        },
    }
    value.update(updates)
    return value


class CapabilitySnapshotTests(unittest.TestCase):
    def test_digest_is_stable_for_equivalent_catalog(self):
        first = snapshot()
        second = CAPABILITIES.build_snapshot({key: value for key, value in first.items() if key != "digest"})
        self.assertEqual(first["digest"], second["digest"])

    def test_duplicate_model_ids_are_rejected(self):
        catalog = snapshot()
        catalog["models"].append(dict(catalog["models"][0]))
        catalog.pop("digest")
        with self.assertRaisesRegex(ValueError, "duplicate model id"):
            CAPABILITIES.build_snapshot(catalog)

    def test_live_runtime_source_and_freshness_are_fail_closed(self):
        catalog = snapshot()
        catalog["source"] = "manual-claim"
        catalog.pop("digest")
        with self.assertRaisesRegex(ValueError, "source must be one of"):
            CAPABILITIES.build_snapshot(catalog)
        runtime = snapshot()
        runtime["source"] = CAPABILITIES.RUNTIME_SOURCE
        runtime["captured_at"] = "2026-08-16T00:00:00Z"
        runtime = CAPABILITIES.build_snapshot({key: value for key, value in runtime.items() if key != "digest"})
        errors = CAPABILITIES.validate_runtime_provenance(
            runtime,
            max_age_seconds=300,
            now=datetime(2026, 8, 16, 0, 10, tzinfo=timezone.utc),
        )
        self.assertIn("runtime capability snapshot is stale", errors)

    def test_routing_validator_rejects_stale_and_fixture_snapshots(self):
        stale = snapshot()
        stale["captured_at"] = "2026-08-16T00:00:00Z"
        stale = CAPABILITIES.build_snapshot({key: value for key, value in stale.items() if key != "digest"})
        value = decision(stale)
        errors = ROUTING.validate(
            value,
            stale,
            now=datetime(2026, 8, 16, 0, 10, tzinfo=timezone.utc),
        )
        self.assertIn("runtime capability snapshot is stale", errors)
        fixture = snapshot()
        fixture["source"] = "caps-test-fixture"
        fixture = CAPABILITIES.build_snapshot({key: value for key, value in fixture.items() if key != "digest"})
        self.assertIn(
            "test fixture capability snapshots cannot authorize live routing",
            ROUTING.validate(decision(fixture), fixture),
        )


class DynamicRoutingTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = snapshot()

    def assertInvalid(self, value: dict, message: str):
        self.assertIn(message, ROUTING.validate(value, self.capabilities))

    def test_runtime_supported_non_56_model_is_valid(self):
        self.assertEqual(ROUTING.validate(decision(self.capabilities), self.capabilities), [])

    def test_model_and_reasoning_must_be_in_runtime_snapshot(self):
        self.assertInvalid(
            decision(self.capabilities, requested_model="missing", resolved_model="missing"),
            "requested route is not supported by the capability snapshot",
        )
        self.assertInvalid(
            decision(self.capabilities, requested_thinking="high", resolved_thinking="high"),
            "requested route is not supported by the capability snapshot",
        )

    def test_snapshot_digest_must_match(self):
        self.assertInvalid(
            decision(self.capabilities, capability_snapshot_digest="sha256:" + "0" * 64),
            "capability_snapshot_digest does not match the supplied snapshot",
        )

    def test_silent_substitution_is_rejected(self):
        self.assertInvalid(
            decision(self.capabilities, resolved_model="gpt-5.6-sol"),
            "an explicit route_resolution is required when requested and resolved routes differ",
        )

    def test_explicit_fallback_records_an_unavailable_requested_route(self):
        value = decision(
            self.capabilities,
            requested_model="missing-model",
            route_resolution={
                "reason": "unsupported_model",
                "limitation": "The live catalog does not expose the requested model.",
            },
        )
        self.assertEqual(ROUTING.validate(value, self.capabilities), [])
        value = decision(
            self.capabilities,
            requested_model="gpt-5.6-sol",
            route_resolution={"reason": "policy_blocked", "limitation": "An invented limitation."},
        )
        self.assertInvalid(
            value,
            "explicit rerouting is allowed only when the requested route is unavailable or blocked",
        )

    def test_daybreak_requires_live_entitled_policy_allowed_specialist_match(self):
        valid = decision(
            self.capabilities,
            task_class="research_strategy",
            requested_model="daybreak-research",
            requested_thinking="high",
            resolved_model="daybreak-research",
            resolved_thinking="high",
        )
        self.assertEqual(ROUTING.validate(valid, self.capabilities), [])
        blocked = snapshot()
        blocked["models"][2]["entitled"] = False
        blocked = CAPABILITIES.build_snapshot({key: value for key, value in blocked.items() if key != "digest"})
        invalid = dict(valid, capability_snapshot_digest=blocked["digest"])
        self.assertInvalidWithSnapshot(invalid, blocked, "Daybreak route must be live, entitled, and allowed by policy")

    def assertInvalidWithSnapshot(self, value: dict, capabilities: dict, message: str):
        self.assertIn(message, ROUTING.validate(value, capabilities))

    def test_inherited_route_must_equal_parent_route(self):
        inherited = decision(
            self.capabilities,
            route_source="inherited",
            parent_route={
                "model": "gpt-next-code",
                "thinking": "medium",
                "capability_snapshot_digest": self.capabilities["digest"],
            },
        )
        self.assertEqual(ROUTING.validate(inherited, self.capabilities), [])
        inherited["parent_route"]["thinking"] = "low"
        self.assertInvalid(inherited, "inherited route must exactly match the parent route")

    def test_full_history_forks_inherit_and_cannot_override_parent_route(self):
        selected = decision(self.capabilities, fork_turns="all")
        self.assertInvalid(selected, "full-history forks must inherit the parent route")
        inherited = decision(
            self.capabilities,
            fork_turns="all",
            route_source="inherited",
            parent_route={
                "model": "gpt-next-code",
                "thinking": "medium",
                "capability_snapshot_digest": self.capabilities["digest"],
            },
        )
        self.assertEqual(ROUTING.validate(inherited, self.capabilities), [])
        inherited["resolved_thinking"] = "high"
        self.assertInvalid(inherited, "inherited route must exactly match the parent route")

    def test_ultra_is_root_only(self):
        self.assertInvalid(
            decision(
                self.capabilities,
                requested_model="gpt-5.6-sol",
                requested_thinking="ultra",
                resolved_model="gpt-5.6-sol",
                resolved_thinking="ultra",
            ),
            "ultra is root-only",
        )

    def test_nesting_is_explicit_and_depth_is_at_most_two(self):
        self.assertInvalid(decision(self.capabilities, delegation_depth=3), "delegation_depth must be between 0 and 2")
        self.assertInvalid(
            decision(self.capabilities, delegation_depth=2, nested_delegation=True),
            "nested delegation cannot be enabled at depth 2",
        )

    def test_workers_have_local_reversible_authority_ceiling(self):
        value = decision(self.capabilities)
        value["task_snapshot"] = dict(value["task_snapshot"], side_effects="external_reversible")
        self.assertInvalid(value, "worker authority cannot exceed local_reversible side effects")
        value = decision(self.capabilities)
        value["authority"]["ceiling"] = "external_reversible"
        self.assertInvalid(value, "worker authority ceiling cannot exceed local_reversible")
        value = decision(self.capabilities)
        value["authority"]["allowed_actions"].append("durable_thread_control")
        self.assertInvalid(value, "worker authority contains an action above the local-reversible ceiling")
        for prohibited in ROUTING.REQUIRED_WORKER_PROHIBITIONS:
            value = decision(self.capabilities)
            value["authority"]["prohibited_actions"].remove(prohibited)
            self.assertTrue(any("worker authority is missing mandatory prohibitions" in error for error in ROUTING.validate(value, self.capabilities)))

    def test_every_specialist_model_requires_a_matching_task_class(self):
        specialist = snapshot()
        specialist["models"][1]["specialist_task_classes"] = ["proof_review"]
        specialist = CAPABILITIES.build_snapshot({key: value for key, value in specialist.items() if key != "digest"})
        value = decision(specialist)
        self.assertInvalidWithSnapshot(value, specialist, "specialist route must match an advertised specialist task class")

    def test_worker_kind_is_explicit(self):
        self.assertInvalid(decision(self.capabilities, worker_kind="background_job"), "invalid worker_kind")

    def test_fanout_starts_at_four_and_scales_to_ten_only_for_safe_lanes(self):
        base = decision(self.capabilities)
        base["fanout"] = dict(base["fanout"], requested_workers=4, independent=False)
        self.assertEqual(ROUTING.validate(base, self.capabilities), [])
        scaled = decision(self.capabilities)
        scaled["fanout"] = dict(scaled["fanout"], requested_workers=10)
        self.assertEqual(ROUTING.validate(scaled, self.capabilities), [])
        unsafe = decision(self.capabilities)
        unsafe["fanout"] = dict(unsafe["fanout"], requested_workers=5, noncolliding=False)
        self.assertInvalid(unsafe, "fanout above 4 requires independent, deterministic, noncolliding lanes")
        too_many = decision(self.capabilities)
        too_many["fanout"] = dict(too_many["fanout"], requested_workers=11)
        self.assertInvalid(too_many, "fanout cannot exceed 10")


if __name__ == "__main__":
    unittest.main()
