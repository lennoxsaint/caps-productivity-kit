#!/usr/bin/env python3
"""Deterministic policy engine for CAPS pinned-thread title synchronization.

The Codex automation supplies evidence-backed thread snapshots and performs
native thread-control calls. This helper decides whether a rename is allowed and
records redacted results. It never mutates Codex state files.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


COMPLETION_WORDS = {
    "CLOSED", "COMPLETE", "COMPLETED", "DEPLOYED", "DONE", "LIVE", "MERGED",
    "RELEASED", "RESOLVED", "SHIPPED",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_audit(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def configured_emojis(config: dict[str, Any], thread_state: dict[str, Any]) -> list[str]:
    values = []
    for mapping_name in ("project_emojis", "category_emojis"):
        mapping = config.get(mapping_name, {})
        if isinstance(mapping, dict):
            values.extend(str(item) for item in mapping.values() if item)
    for value in (config.get("default_emoji"), thread_state.get("manual_emoji_override")):
        if value:
            values.append(str(value))
    return sorted(set(values), key=len, reverse=True)


def strip_known_emoji(title: str, emojis: list[str]) -> str:
    result = title.strip()
    for emoji in emojis:
        if result.startswith(emoji):
            return result[len(emoji):].lstrip(" \t-:")
    return result


def normalize_action_title(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip(" \t\r\n-:;,.!?")
    text = re.sub(r"^(please|pls|can you|could you|help me)\b[:\s,-]*", "", text, flags=re.IGNORECASE)
    text = text.upper() or "UNTITLED THREAD"
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" -:;,.!?") or text[:max_chars].rstrip()


def choose_emoji(thread: dict[str, Any], config: dict[str, Any], thread_state: dict[str, Any]) -> str:
    explicit = thread.get("manual_emoji_override")
    if explicit is not None:
        return str(explicit)
    if "manual_emoji_override" in thread_state:
        return str(thread_state.get("manual_emoji_override") or "")
    project = str(thread.get("project") or "")
    category = str(thread.get("category") or "")
    project_map = config.get("project_emojis", {})
    category_map = config.get("category_emojis", {})
    if isinstance(project_map, dict) and project in project_map:
        return str(project_map[project])
    if isinstance(category_map, dict) and category in category_map:
        return str(category_map[category])
    return str(config.get("default_emoji") or "")


def has_unverified_completion_claim(title: str, completion_verified: bool) -> bool:
    words = set(re.findall(r"[A-Z]+", title.upper()))
    return bool(words & COMPLETION_WORDS) and not completion_verified


def skip(thread_id: str, reason: str) -> dict[str, Any]:
    return {"thread_id": thread_id, "action": "skip", "reason": reason}


def evaluate_thread(
    thread: dict[str, Any],
    config: dict[str, Any],
    state: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    thread_id = str(thread.get("thread_id") or "")
    if not thread_id:
        return skip("", "missing_thread_id")
    if not config.get("enabled", True):
        return skip(thread_id, "globally_disabled")
    if not thread.get("pinned"):
        return skip(thread_id, "not_pinned")
    if not thread.get("active"):
        return skip(thread_id, "not_active")
    if thread.get("opt_out"):
        return skip(thread_id, "thread_opt_out")
    if str(thread.get("project") or "") in set(config.get("opt_out_projects", [])):
        return skip(thread_id, "project_opt_out")

    thread_state = state.get("threads", {}).get(thread_id, {})
    if thread.get("manual_title_override") is not None or thread_state.get("manual_title_override") is not None:
        return skip(thread_id, "manual_title_override")

    current_title = str(thread.get("current_title") or "").strip()
    last_applied_title = str(thread_state.get("last_applied_title") or "").strip()
    if last_applied_title and current_title != last_applied_title:
        return skip(thread_id, "manual_title_change_detected")
    if not thread.get("material_change"):
        return skip(thread_id, "no_material_change")
    evidence_refs = thread.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return skip(thread_id, "missing_evidence")
    state_revision = str(thread.get("state_revision") or "")
    if not state_revision:
        return skip(thread_id, "missing_state_revision")
    if state_revision == str(thread_state.get("last_state_revision") or ""):
        return skip(thread_id, "state_already_reconciled")

    proposed = str(thread.get("proposed_action_title") or "")
    if not proposed.strip():
        return skip(thread_id, "missing_proposed_title")
    if has_unverified_completion_claim(proposed, bool(thread.get("completion_verified"))):
        return skip(thread_id, "unverified_completion_claim")

    interval = timedelta(minutes=max(1, int(config.get("min_rename_interval_minutes", 20))))
    last_renamed = parse_time(thread_state.get("last_auto_rename_at"))
    if last_renamed and now - last_renamed < interval:
        return skip(thread_id, "rename_rate_limited")
    today = now.date().isoformat()
    daily_count = int(thread_state.get("daily_count", 0)) if thread_state.get("daily_date") == today else 0
    if daily_count >= int(config.get("max_auto_renames_per_day", 12)):
        return skip(thread_id, "daily_rename_limit")

    max_chars = max(12, int(config.get("max_title_chars", 48)))
    emoji = choose_emoji(thread, config, thread_state)
    body_limit = max_chars - len(emoji) - (1 if emoji else 0)
    body = normalize_action_title(
        strip_known_emoji(proposed, configured_emojis(config, thread_state)),
        max(8, body_limit),
    )
    current_body = normalize_action_title(
        strip_known_emoji(current_title, configured_emojis(config, thread_state)),
        max(8, body_limit),
    )
    if current_body == body:
        return skip(thread_id, "title_already_current")
    desired = f"{emoji} {body}".strip()
    fingerprint_source = "\0".join((thread_id, desired, state_revision))
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint == thread_state.get("last_fingerprint"):
        return skip(thread_id, "rename_already_applied")
    return {
        "thread_id": thread_id,
        "action": "rename",
        "reason": "material_evidence_supported_change",
        "old_title": current_title,
        "desired_title": desired,
        "state_revision": state_revision,
        "fingerprint": fingerprint,
        "evidence_refs": [str(item) for item in evidence_refs],
    }


def evaluate(payload: dict[str, Any], config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    now = parse_time(payload.get("observed_at")) or utc_now()
    threads = payload.get("threads")
    if not isinstance(threads, list):
        raise ValueError("payload.threads must be a list")
    return {
        "schema_version": "1.0",
        "observed_at": now.isoformat(),
        "decisions": [evaluate_thread(thread, config, state, now) for thread in threads],
    }


def record_result(
    state: dict[str, Any],
    result: dict[str, Any],
    observed_at: datetime,
) -> dict[str, Any]:
    thread_id = str(result.get("thread_id") or "")
    if not thread_id:
        raise ValueError("result.thread_id is required")
    outcome = str(result.get("outcome") or "")
    if outcome not in {"renamed", "unchanged", "failed", "manual_override", "override_cleared"}:
        raise ValueError("unsupported result.outcome")
    threads = state.setdefault("threads", {})
    thread_state = threads.setdefault(thread_id, {})
    if outcome == "renamed":
        thread_state["last_applied_title"] = str(result["desired_title"])
        thread_state["last_auto_rename_at"] = observed_at.isoformat()
        thread_state["last_state_revision"] = str(result["state_revision"])
        thread_state["last_fingerprint"] = str(result["fingerprint"])
        today = observed_at.date().isoformat()
        if thread_state.get("daily_date") != today:
            thread_state["daily_date"] = today
            thread_state["daily_count"] = 0
        thread_state["daily_count"] = int(thread_state.get("daily_count", 0)) + 1
    elif outcome == "manual_override":
        if "manual_title_override" in result:
            thread_state["manual_title_override"] = result.get("manual_title_override")
        if "manual_emoji_override" in result:
            thread_state["manual_emoji_override"] = result.get("manual_emoji_override")
    elif outcome == "override_cleared":
        thread_state.pop("manual_title_override", None)
        thread_state.pop("manual_emoji_override", None)
        thread_state["last_applied_title"] = str(result.get("current_title") or "")
    if outcome == "unchanged" and result.get("state_revision"):
        thread_state["last_state_revision"] = str(result["state_revision"])
    thread_state["last_outcome"] = outcome
    thread_state["last_observed_at"] = observed_at.isoformat()
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--config", type=Path, required=True)
    evaluate_parser.add_argument("--state", type=Path, required=True)
    record_parser = sub.add_parser("record")
    record_parser.add_argument("--state", type=Path, required=True)
    record_parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    payload = json.load(sys.stdin)
    if args.command == "evaluate":
        config = load_json(args.config, {})
        state = load_json(args.state, {"schema_version": "1.0", "threads": {}})
        print(json.dumps(evaluate(payload, config, state), indent=2, sort_keys=True, ensure_ascii=False))
        return

    state = load_json(args.state, {"schema_version": "1.0", "threads": {}})
    result = payload.get("result")
    if not isinstance(result, dict):
        raise SystemExit("payload.result must be an object")
    observed_at = parse_time(payload.get("observed_at")) or utc_now()
    record_result(state, result, observed_at)
    atomic_write_json(args.state, state)
    audit = {
        "schema_version": "1.0",
        "observed_at": observed_at.isoformat(),
        "thread_id": str(result.get("thread_id") or ""),
        "outcome": str(result.get("outcome") or ""),
        "reason": str(result.get("reason") or ""),
        "evidence_refs": [str(item) for item in result.get("evidence_refs", [])],
        "error_code": result.get("error_code"),
    }
    append_audit(args.audit, audit)
    print(json.dumps({"status": "recorded", "thread_id": audit["thread_id"], "outcome": audit["outcome"]}))


if __name__ == "__main__":
    main()
