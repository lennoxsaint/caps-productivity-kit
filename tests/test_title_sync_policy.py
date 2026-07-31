from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "title_sync_policy",
    ROOT / "scripts/title-sync-policy.py",
)
POLICY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(POLICY)


NOW = datetime(2026, 7, 31, 1, 0, tzinfo=timezone.utc)


def config() -> dict:
    return {
        "enabled": True,
        "max_title_chars": 48,
        "min_rename_interval_minutes": 20,
        "max_auto_renames_per_day": 12,
        "default_emoji": "",
        "project_emojis": {"duo": "🚀"},
        "category_emojis": {"build": "🛠️"},
        "opt_out_projects": [],
    }


def thread(**overrides) -> dict:
    value = {
        "thread_id": "thread-1",
        "current_title": "BUILD OLD FLOW",
        "pinned": True,
        "active": True,
        "project": "duo",
        "category": "build",
        "material_change": True,
        "evidence_refs": ["test-pass"],
        "state_revision": "rev-2",
        "proposed_action_title": "build safer update flow",
        "completion_verified": False,
    }
    value.update(overrides)
    return value


class TitleSyncPolicyTests(unittest.TestCase):
    def test_project_emoji_precedes_category(self):
        decision = POLICY.evaluate_thread(thread(), config(), {"threads": {}}, NOW)
        self.assertEqual(decision["action"], "rename")
        self.assertEqual(decision["desired_title"], "🚀 BUILD SAFER UPDATE FLOW")

    def test_manual_emoji_override_persists(self):
        state = {"threads": {"thread-1": {"manual_emoji_override": "🧠"}}}
        decision = POLICY.evaluate_thread(thread(), config(), state, NOW)
        self.assertEqual(decision["desired_title"], "🧠 BUILD SAFER UPDATE FLOW")

    def test_manual_title_override_blocks_automation(self):
        state = {"threads": {"thread-1": {"manual_title_override": "MY WORDING"}}}
        decision = POLICY.evaluate_thread(thread(), config(), state, NOW)
        self.assertEqual(decision["reason"], "manual_title_override")

    def test_manual_title_change_after_auto_rename_is_preserved(self):
        state = {"threads": {"thread-1": {"last_applied_title": "🚀 BUILD OLD FLOW"}}}
        decision = POLICY.evaluate_thread(thread(current_title="OWNER WORDING"), config(), state, NOW)
        self.assertEqual(decision["reason"], "manual_title_change_detected")

    def test_requires_material_change_and_evidence(self):
        no_change = POLICY.evaluate_thread(thread(material_change=False), config(), {"threads": {}}, NOW)
        no_evidence = POLICY.evaluate_thread(thread(evidence_refs=[]), config(), {"threads": {}}, NOW)
        self.assertEqual(no_change["reason"], "no_material_change")
        self.assertEqual(no_evidence["reason"], "missing_evidence")

    def test_refuses_unverified_completion_claim(self):
        decision = POLICY.evaluate_thread(
            thread(proposed_action_title="SHIPPED UPDATE FLOW"),
            config(),
            {"threads": {}},
            NOW,
        )
        self.assertEqual(decision["reason"], "unverified_completion_claim")

    def test_recorded_revision_makes_event_and_sweep_idempotent(self):
        state = {"schema_version": "1.0", "threads": {}}
        first = POLICY.evaluate_thread(thread(), config(), state, NOW)
        POLICY.record_result(
            state,
            {
                **first,
                "outcome": "renamed",
            },
            NOW,
        )
        second = POLICY.evaluate_thread(
            thread(current_title=first["desired_title"]),
            config(),
            state,
            NOW,
        )
        self.assertEqual(second["reason"], "state_already_reconciled")

    def test_rate_limit_blocks_distinct_revision(self):
        state = {
            "threads": {
                "thread-1": {
                    "last_applied_title": "BUILD OLD FLOW",
                    "last_auto_rename_at": "2026-07-31T00:50:00+00:00",
                    "last_state_revision": "rev-1",
                }
            }
        }
        decision = POLICY.evaluate_thread(thread(), config(), state, NOW)
        self.assertEqual(decision["reason"], "rename_rate_limited")

    def test_state_write_is_atomic_and_audit_is_redacted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "state.json"
            audit_path = root / "audit.jsonl"
            state = {"schema_version": "1.0", "threads": {}}
            result = {
                "thread_id": "thread-1",
                "outcome": "manual_override",
                "manual_title_override": "OWNER WORDING",
                "reason": "user_event",
                "evidence_refs": [],
            }
            POLICY.record_result(state, result, NOW)
            POLICY.atomic_write_json(state_path, state)
            POLICY.append_audit(
                audit_path,
                {
                    "thread_id": "thread-1",
                    "outcome": "manual_override",
                    "reason": "user_event",
                    "evidence_refs": [],
                },
            )
            self.assertEqual(POLICY.load_json(state_path, {})["threads"]["thread-1"]["manual_title_override"], "OWNER WORDING")
            self.assertNotIn("OWNER WORDING", audit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
