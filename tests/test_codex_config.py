from __future__ import annotations

import importlib.util
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "codex_config", ROOT / "scripts/codex-config.py"
)
CONFIG = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = CONFIG
SPEC.loader.exec_module(CONFIG)


class CodexConfigTests(unittest.TestCase):
    def test_plan_diff_does_not_expose_neighbor_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text('model = "old"\nowner_data = "private-neighbor"\n')
            plan = CONFIG.plan_config(path, replacements=[("model", "gpt-6-astra")])
            self.assertNotIn("private-neighbor", plan.primary.diff)

    def test_later_target_drift_preserves_owner_and_recovers_prior_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary, role = root / 'config.toml', root / 'role.toml'
            primary.write_text('model = "old"\n')
            role.write_text('model = "old"\ninstructions = "keep"\n')
            before = primary.read_bytes()
            plan = CONFIG.plan_config(primary, replacements=[('model', 'gpt-6-astra')], specialist_configs=[role])
            original_write = CONFIG._atomic_write
            owner = b'model = "owner"\ninstructions = "keep"\n'
            def write_then_owner_edit(path, payload, mode=None):
                original_write(path, payload, mode)
                if path == primary.resolve():
                    role.write_bytes(owner)
            with patch.object(CONFIG, '_atomic_write', side_effect=write_then_owner_edit):
                with self.assertRaisesRegex(CONFIG.ConfigError, 'hash_drift'):
                    CONFIG.apply_plan(plan, {p.path: p.before_hash for p in plan.files})
            self.assertEqual(primary.read_bytes(), before)
            self.assertEqual(role.read_bytes(), owner)

    def test_global_scope_uses_supplied_codex_home_as_config_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            expected = codex_home / "config.toml"
            resolved = CONFIG.resolve_config_path(project=codex_home, scope="global")
            self.assertEqual(resolved, expected.resolve())
            self.assertNotEqual(resolved, (codex_home / ".codex/config.toml").resolve())

    def test_legacy_multi_agent_cap_requires_explicit_replacement(self):
        original = '''model = "gpt-6-astra"
model_reasoning_effort = "low"

[agents]
enabled = true
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "max"
max_concurrent_threads_per_session = 6

[features.multi_agent_v2]
enabled = true
max_concurrent_threads_per_session = 11
unrelated = "keep"
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text(original, encoding="utf-8")
            before = path.read_bytes()

            no_op = CONFIG.plan_config(path, add_missing=True)
            self.assertFalse(any(item.changed for item in no_op.files))
            self.assertEqual(path.read_bytes(), before)

            plan = CONFIG.plan_config(
                path,
                replacements=[
                    (
                        "features.multi_agent_v2.max_concurrent_threads_per_session",
                        6,
                    )
                ],
            )
            self.assertEqual(
                plan.primary.changed_keys,
                ["features.multi_agent_v2.max_concurrent_threads_per_session"],
            )
            CONFIG.apply_plan(plan, {plan.primary.path: plan.primary.before_hash})
            data = CONFIG.parse_toml(path.read_text(encoding="utf-8"), path)
            self.assertTrue(data["features"]["multi_agent_v2"]["enabled"])
            self.assertEqual(
                data["features"]["multi_agent_v2"]["max_concurrent_threads_per_session"],
                6,
            )
            self.assertEqual(
                data["features"]["multi_agent_v2"]["unrelated"], "keep"
            )
            self.assertEqual(data["agents"]["enabled"], True)

    def test_unsupported_feature_setting_is_not_replaceable(self):
        with self.assertRaisesRegex(
            CONFIG.ConfigError, "replacement_key_not_allowed"
        ):
            CONFIG.parse_replacement("features.multi_agent_v2.enabled=false")

    def test_fresh_defaults_use_supported_root_thread_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".codex" / "config.toml"
            plan = CONFIG.plan_config(path)
            data = CONFIG.parse_toml(plan.primary.proposed_text, path)
            self.assertEqual(data["model"], "gpt-6-astra")
            self.assertEqual(data["model_reasoning_effort"], "low")
            self.assertNotIn("models", data)
            self.assertEqual(data["agents"]["max_concurrent_threads_per_session"], 6)

    def test_plan_output_omits_candidate_text_unless_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            before = b'model = "gpt-5.6-sol"\n'
            path.write_bytes(before)
            plan = CONFIG.plan_config(path, replacements=[("model", "gpt-6-astra")])
            self.assertEqual(path.read_bytes(), before)

            payload = plan.as_dict(redact=True)
            self.assertNotIn("proposed_text", payload)
            self.assertNotIn("proposed_text", payload["files"][0])
            rendered = CONFIG._format_text(payload)
            self.assertIn("Exact diff:", rendered)
            self.assertNotIn("Proposed text:", rendered)

            requested = plan.as_dict(redact=True, include_proposed=True)
            self.assertIn("proposed_text", requested)
            self.assertIn("proposed_text", requested["files"][0])
            self.assertIn("Proposed text:", CONFIG._format_text(requested, include_proposed=True))

    def test_malformed_toml_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            malformed = b'model = [\n'
            path.write_bytes(malformed)
            with self.assertRaisesRegex(CONFIG.ConfigError, "invalid_toml"):
                CONFIG.plan_config(path, replacements=[("model", "gpt-6-astra")])
            self.assertEqual(path.read_bytes(), malformed)

    def test_apply_refuses_a_hash_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text('model = "gpt-5.6-sol"\n', encoding="utf-8")
            plan = CONFIG.plan_config(path, replacements=[("model", "gpt-6-astra")])
            owner_edit = b'model = "owner-choice"\n'
            path.write_bytes(owner_edit)
            with self.assertRaisesRegex(CONFIG.ConfigError, "hash_drift"):
                CONFIG.apply_plan(plan, {plan.primary.path: plan.primary.before_hash})
            self.assertEqual(path.read_bytes(), owner_edit)

    def test_rollback_refuses_a_later_owner_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            original = b'model = "gpt-5.6-sol"\n'
            path.write_bytes(original)
            plan = CONFIG.plan_config(path, replacements=[("model", "gpt-6-astra")])
            applied = CONFIG.apply_plan(plan, {plan.primary.path: plan.primary.before_hash})
            backup = Path(applied["backups"][0])
            later_edit = path.read_bytes() + b"# owner edit after apply\n"
            path.write_bytes(later_edit)
            with self.assertRaisesRegex(CONFIG.ConfigError, "hash_drift"):
                CONFIG.rollback_file(path, backup, plan.primary.proposed_hash)
            self.assertEqual(path.read_bytes(), later_edit)

    def test_standalone_specialist_cleanup_preserves_permissions_and_multiline_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.toml"
            config_path.write_text('model = "gpt-6-astra"\n', encoding="utf-8")
            role_path = root / "specialist.toml"
            role_bytes = (
                b'model = "gpt-5.6-sol"\n'
                b'model_reasoning_effort = "xhigh"\n'
                b'instructions = """Keep this exact line.\n'
                b"Keep # comments and a second line, too.\n"
                b'"""\n'
                b"[permissions]\n"
                b'network = "none"\n'
            )
            role_path.write_bytes(role_bytes)
            role_path.chmod(0o640)
            original_mode = stat.S_IMODE(role_path.stat().st_mode)
            instruction_bytes = (
                b'instructions = """Keep this exact line.\n'
                b"Keep # comments and a second line, too.\n"
                b'"""\n'
            )
            plan = CONFIG.plan_config(config_path, specialist_configs=[role_path])
            role_plan = plan.files[1]
            self.assertEqual(role_plan.changed_keys, ["model", "model_reasoning_effort"])
            CONFIG.apply_plan(
                plan,
                {
                    item.path: item.before_hash
                    for item in plan.files
                },
            )
            updated = role_path.read_bytes()
            self.assertNotIn(b'model = "gpt-5.6-sol"', updated)
            self.assertNotIn(b'model_reasoning_effort = "xhigh"', updated)
            self.assertIn(instruction_bytes, updated)
            self.assertIn(b'[permissions]\nnetwork = "none"\n', updated)
            self.assertEqual(stat.S_IMODE(role_path.stat().st_mode), original_mode)


if __name__ == "__main__":
    unittest.main()
