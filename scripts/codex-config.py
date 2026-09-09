#!/usr/bin/env python3
"""Plan and apply narrowly-scoped Codex configuration changes.

The default operation is a read-only plan. A fresh project config receives the
managed defaults for new interactive threads and native subagents. An existing
config is only inspected unless the caller explicitly requests a replacement,
specialist cleanup, or --add-missing.

This module deliberately edits TOML text instead of serialising a parsed
dictionary. That keeps comments, ordering, formatting, and unrelated settings
intact. The apply operation requires an expected hash and writes atomically;
the installer uses it only for a missing project config.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


try:  # Python 3.11+.
    import tomllib as _toml
except ModuleNotFoundError:  # Python 3.9/3.10 when the optional tomli package exists.
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        _toml = None  # type: ignore


MISSING_HASH = "missing"

# These are the only defaults this helper owns. In particular, service_tier is
# intentionally absent: Codex should keep its standard/default tier.
DEFAULT_VALUES: Dict[str, Any] = {
    "model": "gpt-6-astra",
    "model_reasoning_effort": "low",
    "agents.enabled": True,
    "agents.default_subagent_model": "gpt-5.6-luna",
    "agents.default_subagent_reasoning_effort": "max",
    "agents.max_concurrent_threads_per_session": 6,
}

DEFAULT_CONFIG_TEXT = """# CAPS defaults for new interactive Codex threads.
# The service tier is intentionally not set; Codex keeps its standard/default.

model = "gpt-6-astra"
model_reasoning_effort = "low"

[agents]
enabled = true
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "max"
max_concurrent_threads_per_session = 6
"""

_BARE_KEY = r"[A-Za-z0-9_-]+"
_KEY_RE = re.compile(
    r"^\s*((?:" + _BARE_KEY + r")(?:\.(?:" + _BARE_KEY + r"))*)\s*="
)
_TABLE_RE = re.compile(r"^\s*(\[\[?)([^\]]+)(\]\]?)\s*$")
_SAFE_REPLACEMENT_PATHS = {
    "model",
    "model_reasoning_effort",
    "agents.enabled",
    "agents.default_subagent_model",
    "agents.default_subagent_reasoning_effort",
    "agents.max_concurrent_threads_per_session",
    # Codex releases may expose the session cap through this legacy feature
    # table. It is replaceable only when the owner explicitly names it.
    "features.multi_agent_v2.max_concurrent_threads_per_session",
    # Keep the legacy alias replaceable for an explicit owner migration, but
    # never add it automatically.
    "agents.max_threads",
}
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(token|password|secret|api[_-]?key|authorization|bearer|private[_-]?key|credential)"
)


class ConfigError(RuntimeError):
    """A fail-closed configuration planning or apply error."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _parser_available() -> bool:
    return _toml is not None


def parse_toml(text: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """Parse and validate a TOML document without exposing its values."""

    if _toml is None:
        location = str(path) if path else "the config"
        raise ConfigError(
            "toml_parser_unavailable: Python 3.11+ or the tomli package is "
            "required to inspect " + location
        )
    try:
        value = _toml.loads(text)
    except Exception as error:  # tomllib/tomli use different exception classes.
        location = str(path) if path else "config"
        raise ConfigError("invalid_toml: " + location) from error
    if not isinstance(value, dict):
        raise ConfigError("invalid_toml_root")
    return value


def _read_state(path: Path) -> Tuple[bytes, str, bool]:
    if not path.exists():
        return b"", "", False
    if not path.is_file():
        raise ConfigError("config_path_not_a_file: " + str(path))
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError("config_not_utf8: " + str(path)) from error
    except OSError as error:
        raise ConfigError("config_read_failed: " + str(path)) from error
    return raw, text, True


def _before_hash(raw: bytes, exists: bool) -> str:
    return sha256_bytes(raw) if exists else MISSING_HASH


def _path_parts(path: str) -> Tuple[str, ...]:
    parts = tuple(path.split("."))
    if not parts or any(not re.fullmatch(_BARE_KEY, part) for part in parts):
        raise ConfigError("invalid_config_key")
    return parts


def _lookup(mapping: Mapping[str, Any], parts: Sequence[str]) -> Any:
    current: Any = mapping
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _is_allowed_replacement(path: str) -> bool:
    if path in _SAFE_REPLACEMENT_PATHS:
        return True
    parts = path.split(".")
    # Role files may be represented inline under [agents.<role>]. Only model
    # and effort are replaceable; instructions, sandbox, and MCP permissions
    # remain owner-controlled and cannot be changed by this helper.
    return (
        len(parts) == 3
        and parts[0] == "agents"
        and re.fullmatch(_BARE_KEY, parts[1]) is not None
        and parts[2] in {"model", "model_reasoning_effort"}
    )


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        raise ConfigError("replacement_value_missing")

    # A convenient unquoted model name is accepted as a string. TOML values
    # that are explicitly quoted or typed are still validated by the parser.
    if _toml is None:
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
            return float(value)
        if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            return value[1:-1]
        return value

    candidate = value
    if value[:1] not in {'"', "'", "[", "{"} and value.lower() not in {
        "true",
        "false",
    } and not re.fullmatch(r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?", value):
        candidate = json.dumps(value)
    try:
        parsed = _toml.loads("value = " + candidate)
    except Exception as error:
        raise ConfigError("invalid_replacement_value") from error
    result = parsed.get("value")
    if not isinstance(result, (str, bool, int, float)):
        raise ConfigError("replacement_must_be_scalar")
    return result


def parse_replacement(spec: str) -> Tuple[str, Any]:
    if "=" not in spec:
        raise ConfigError("replacement_requires_key_and_value")
    key, raw = spec.split("=", 1)
    key = key.strip()
    if not _is_allowed_replacement(key):
        raise ConfigError("replacement_key_not_allowed: " + key)
    _path_parts(key)
    return key, _parse_scalar(raw)


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    raise ConfigError("replacement_must_be_scalar")


def _line_parts(line: str) -> Tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1:]
    return line, ""


def _comment_index(text: str) -> int:
    """Return the first TOML comment marker outside a quoted string."""

    quote: Optional[str] = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "#":
            return index
        index += 1
    return len(text)


def _table_header(body: str) -> Optional[Tuple[Tuple[str, ...], bool]]:
    visible = body[: _comment_index(body)].strip()
    match = _TABLE_RE.match(visible)
    if not match:
        return None
    opening, raw_path, closing = match.groups()
    if (opening == "[[") != (closing == "]]"):
        return None
    path = raw_path.strip()
    if not path:
        return None
    try:
        parts = _path_parts(path)
    except ConfigError:
        return None
    return parts, opening == "[["


def _assignment(
    body: str, current_table: Tuple[str, ...]
) -> Optional[Tuple[Tuple[str, ...], int]]:
    visible = body[: _comment_index(body)]
    match = _KEY_RE.match(visible)
    if not match:
        return None
    key = match.group(1)
    return current_table + _path_parts(key), visible.index("=", match.start(1))


def _iter_assignments(text: str) -> Iterable[Tuple[int, Tuple[str, ...], int]]:
    """Yield (line index, absolute dotted key, equals index)."""

    current_table: Tuple[str, ...] = ()
    multiline: Optional[str] = None
    for index, line in enumerate(text.splitlines(keepends=True)):
        body, _ = _line_parts(line)
        if multiline is not None:
            if body.count(multiline) % 2:
                multiline = None
            continue
        header = _table_header(body)
        if header is not None:
            current_table, _ = header
            continue
        assignment = _assignment(body, current_table)
        if assignment is not None:
            absolute, equals = assignment
            yield index, absolute, equals
        triple_counts = {token: body.count(token) for token in ('"""', "'''")}
        for token, count in triple_counts.items():
            if count % 2:
                multiline = token
                break


def _replace_assignment_line(line: str, equals: int, rendered: str) -> str:
    body, ending = _line_parts(line)
    after = body[equals + 1 :]
    comment_at = _comment_index(after)
    value_part = after[:comment_at]
    comment = after[comment_at:]
    stripped = value_part.rstrip(" \t")
    trailing = value_part[len(stripped) :]
    leading = stripped[: len(stripped) - len(stripped.lstrip(" \t"))]
    return body[: equals + 1] + leading + rendered + trailing + comment + ending


def _line_ending(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text and "\n" not in text:
        return "\r"
    return "\n"


def _header_indices(text: str) -> List[Tuple[int, Tuple[str, ...], bool]]:
    current: List[Tuple[int, Tuple[str, ...], bool]] = []
    multiline: Optional[str] = None
    for index, line in enumerate(text.splitlines(keepends=True)):
        body, _ = _line_parts(line)
        if multiline is not None:
            if body.count(multiline) % 2:
                multiline = None
            continue
        header = _table_header(body)
        if header is not None:
            current.append((index, header[0], header[1]))
            continue
        for token in ('"""', "'''"):
            if body.count(token) % 2:
                multiline = token
                break
    return current


def _insert_lines(text: str, index: int, additions: Sequence[str]) -> str:
    lines = text.splitlines(keepends=True)
    ending = _line_ending(text)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += ending
    additions_with_endings = [
        item + ("" if item.endswith(("\n", "\r")) else ending) for item in additions
    ]
    lines[index:index] = additions_with_endings
    return "".join(lines)


def _append_table(
    text: str, table: Tuple[str, ...], assignments: Sequence[Tuple[str, Any]]
) -> str:
    additions: List[str] = []
    ending = _line_ending(text)
    if text and not text.endswith(("\n", "\r")):
        additions.append("")
    if text and text.rstrip("\r\n"):
        # Separate a new table from the preceding value/comment. Avoid
        # duplicating a blank line when the source already ends with one.
        if not text.endswith(ending + ending):
            additions.append("")
    additions.append("[" + ".".join(table) + "]")
    additions.extend(key + " = " + _render_value(value) for key, value in assignments)
    return _insert_lines(text, len(text.splitlines(keepends=True)), additions)


def _insert_assignment(text: str, table: Tuple[str, ...], key: str, value: Any) -> str:
    rendered_line = key + " = " + _render_value(value)
    if not table:
        headers = _header_indices(text)
        insertion = headers[0][0] if headers else len(text.splitlines(keepends=True))
        return _insert_lines(text, insertion, [rendered_line])

    headers = _header_indices(text)
    exact = [item for item in headers if item[1] == table and not item[2]]
    if exact:
        start = exact[0][0]
        end = len(text.splitlines(keepends=True))
        for index, _, _ in headers:
            if index > start:
                end = index
                break
        return _insert_lines(text, end, [rendered_line])

    # A child table such as [agents.specialist] means the parent table does
    # not have a header yet. Insert the parent before that child.
    children = [
        item
        for item in headers
        if len(item[1]) > len(table) and item[1][: len(table)] == table
    ]
    if children:
        return _insert_lines(
            text,
            children[0][0],
            ["[" + ".".join(table) + "]", rendered_line],
        )
    return _append_table(text, table, [(key, value)])


def replace_key(text: str, path: str, value: Any) -> str:
    parts = _path_parts(path)
    matches = [item for item in _iter_assignments(text) if item[1] == parts]
    if len(matches) > 1:
        raise ConfigError("duplicate_config_key: " + path)
    rendered = _render_value(value)
    if matches:
        lines = text.splitlines(keepends=True)
        line_index, _, equals = matches[0]
        lines[line_index] = _replace_assignment_line(lines[line_index], equals, rendered)
        return "".join(lines)
    return _insert_assignment(text, parts[:-1], parts[-1], value)


def remove_keys(text: str, paths: Sequence[str]) -> Tuple[str, List[str]]:
    wanted = {_path_parts(path): path for path in paths}
    matches = [item for item in _iter_assignments(text) if item[1] in wanted]
    if not matches:
        return text, []
    lines = text.splitlines(keepends=True)
    removed = []
    for line_index, absolute, _ in reversed(matches):
        removed.append(wanted[absolute])
        del lines[line_index]
    return "".join(lines), list(reversed(removed))


def _has_header(text: str, table: Tuple[str, ...]) -> bool:
    return any(path == table and not array for _, path, array in _header_indices(text))


def add_missing_defaults(
    text: str, data: Mapping[str, Any], path: Path
) -> Tuple[str, List[str]]:
    """Add only missing defaults that cannot override an explicit legacy key."""

    proposed = text
    changed: List[str] = []

    # Codex reads these as root-level settings. Add only missing values, and
    # leave any existing [models.new_thread] table untouched as owner data.
    for key in ("model", "model_reasoning_effort"):
        if key not in data:
            proposed = replace_key(proposed, key, DEFAULT_VALUES[key])
            changed.append(key)

    agents = data.get("agents")
    if isinstance(agents, Mapping):
        agent_values = (
            ("enabled", "agents.enabled"),
            ("default_subagent_model", "agents.default_subagent_model"),
            ("default_subagent_reasoning_effort", "agents.default_subagent_reasoning_effort"),
        )
        for key, full_path in agent_values:
            if key not in agents:
                proposed = replace_key(proposed, full_path, DEFAULT_VALUES[full_path])
                changed.append(full_path)
        # max_threads is the documented legacy alias. Adding the canonical
        # key beside it would change the effective cap, so preserve the alias.
        if "max_concurrent_threads_per_session" not in agents and "max_threads" not in agents:
            proposed = replace_key(
                proposed,
                "agents.max_concurrent_threads_per_session",
                DEFAULT_VALUES["agents.max_concurrent_threads_per_session"],
            )
            changed.append("agents.max_concurrent_threads_per_session")
    elif agents is None and not _has_header(proposed, ("agents",)):
        proposed = _append_table(
            proposed,
            ("agents",),
            [
                ("enabled", DEFAULT_VALUES["agents.enabled"]),
                ("default_subagent_model", DEFAULT_VALUES["agents.default_subagent_model"]),
                (
                    "default_subagent_reasoning_effort",
                    DEFAULT_VALUES["agents.default_subagent_reasoning_effort"],
                ),
                (
                    "max_concurrent_threads_per_session",
                    DEFAULT_VALUES["agents.max_concurrent_threads_per_session"],
                ),
            ],
        )
        changed.extend(
            (
                "agents.enabled",
                "agents.default_subagent_model",
                "agents.default_subagent_reasoning_effort",
                "agents.max_concurrent_threads_per_session",
            )
        )

    # Validate the edited result before returning.
    parse_toml(proposed, path)
    return proposed, changed


def _role_file_from_config(
    data: Mapping[str, Any], role: str, config_path: Path
) -> Optional[Path]:
    role_data = _lookup(data, ("agents", role))
    if not isinstance(role_data, Mapping):
        return None
    config_file = role_data.get("config_file")
    if not isinstance(config_file, str) or not config_file:
        return None
    candidate = Path(config_file).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def _specialist_paths(role: str) -> Tuple[str, str]:
    _path_parts(role)
    return "agents." + role + ".model", "agents." + role + ".model_reasoning_effort"


@dataclass
class FilePlan:
    path: Path
    before_bytes: bytes
    before_text: str
    before_exists: bool
    proposed_text: str
    changed_keys: List[str]

    @property
    def before_hash(self) -> str:
        return _before_hash(self.before_bytes, self.before_exists)

    @property
    def proposed_bytes(self) -> bytes:
        return self.proposed_text.encode("utf-8")

    @property
    def proposed_hash(self) -> str:
        return sha256_bytes(self.proposed_bytes)

    @property
    def changed(self) -> bool:
        return self.before_bytes != self.proposed_bytes or not self.before_exists

    @property
    def diff(self) -> str:
        before = self.before_text.splitlines(keepends=True)
        after = self.proposed_text.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=str(self.path),
                tofile=str(self.path),
                lineterm="\n",
                n=0,
            )
        )

    def as_dict(
        self, redact: bool = False, include_proposed: bool = False
    ) -> Dict[str, Any]:
        diff = redact_text(self.diff) if redact else self.diff
        result = {
            "path": str(self.path),
            "exists": self.before_exists,
            "before_hash": self.before_hash,
            "before_sha256": None if not self.before_exists else self.before_hash,
            "proposed_hash": self.proposed_hash,
            "diff": diff,
            "changed": self.changed,
            "changed_keys": list(self.changed_keys),
        }
        if include_proposed:
            result["proposed_text"] = (
                redact_text(self.proposed_text) if redact else self.proposed_text
            )
        return result


@dataclass
class ConfigPlan:
    config_path: Path
    scope: str
    files: List[FilePlan]

    @property
    def primary(self) -> FilePlan:
        return self.files[0]

    def as_dict(
        self, redact: bool = False, include_proposed: bool = False
    ) -> Dict[str, Any]:
        primary = self.primary.as_dict(
            redact=redact, include_proposed=include_proposed
        )
        result = {
            "status": "planned",
            "applied": False,
            "scope": self.scope,
            "config_path": str(self.config_path),
            "before_hash": primary["before_hash"],
            "diff": primary["diff"],
            "changed": any(item.changed for item in self.files),
            "changed_keys": primary["changed_keys"],
            "files": [
                item.as_dict(redact=redact, include_proposed=include_proposed)
                for item in self.files
            ],
        }
        if include_proposed:
            result["proposed_text"] = primary["proposed_text"]
        return result


def redact_text(text: str) -> str:
    """Redact likely credential assignment values from CLI output only."""

    lines: List[str] = []
    for line in text.splitlines(keepends=True):
        body, ending = _line_parts(line)
        equals = body.find("=")
        if equals >= 0 and _SENSITIVE_KEY_RE.search(body[:equals]):
            after = body[equals + 1 :]
            comment_at = _comment_index(after)
            comment = after[comment_at:]
            value_part = after[:comment_at]
            whitespace = value_part[: len(value_part) - len(value_part.lstrip(" \t"))]
            body = body[: equals + 1] + whitespace + '"<redacted>"' + comment
        lines.append(body + ending)
    return "".join(lines)


def plan_config(
    path: Path,
    *,
    scope: str = "explicit",
    replacements: Sequence[Tuple[str, Any]] = (),
    remove_specialists: Sequence[str] = (),
    specialist_configs: Sequence[Path] = (),
    add_missing: bool = False,
) -> ConfigPlan:
    """Build a plan without writing any file.

    Existing configs are validated and preserved by default. add_missing is an
    explicit upgrade operation and still never overwrites an existing value.
    Replacements and specialist cleanup are also explicit operations.
    """

    path = path.expanduser().resolve()
    before_bytes, before_text, exists = _read_state(path)
    changed_keys: List[str] = []
    data: Dict[str, Any] = {}
    if exists:
        data = parse_toml(before_text, path)
        proposed = before_text
        if add_missing:
            proposed, added = add_missing_defaults(proposed, data, path)
            changed_keys.extend(added)
    else:
        proposed = DEFAULT_CONFIG_TEXT

    for key, value in replacements:
        next_text = replace_key(proposed, key, value)
        if next_text != proposed:
            changed_keys.append(key)
        proposed = next_text

    # Inline role declarations are safe to clean because only model/effort
    # assignments are removed. Description, instructions, sandbox, and MCP
    # permission keys remain untouched.
    role_files: List[Path] = []
    for role in remove_specialists:
        model_path, effort_path = _specialist_paths(role)
        proposed, removed = remove_keys(proposed, (model_path, effort_path))
        changed_keys.extend(removed)
        referenced = _role_file_from_config(data, role, path) if exists else None
        if referenced is not None:
            role_files.append(referenced)
    role_files.extend(item.expanduser().resolve() for item in specialist_configs)

    if exists or _parser_available():
        parse_toml(proposed, path)
    primary = FilePlan(
        path=path,
        before_bytes=before_bytes,
        before_text=before_text,
        before_exists=exists,
        proposed_text=proposed,
        changed_keys=changed_keys,
    )
    files = [primary]

    # A referenced custom role file is its own TOML document. It is included
    # in the same plan so an owner can review every exact diff before apply.
    seen = {path}
    for role_path in role_files:
        if role_path in seen:
            continue
        seen.add(role_path)
        role_bytes, role_text, role_exists = _read_state(role_path)
        if not role_exists:
            raise ConfigError("specialist_config_missing: " + str(role_path))
        parse_toml(role_text, role_path)
        role_proposed, removed = remove_keys(
            role_text,
            ("model", "model_reasoning_effort"),
        )
        # Keep the parse gate even when no stale key is present, so all files
        # named by the plan are known-valid before any apply can begin.
        parse_toml(role_proposed, role_path)
        files.append(
            FilePlan(
                path=role_path,
                before_bytes=role_bytes,
                before_text=role_text,
                before_exists=True,
                proposed_text=role_proposed,
                changed_keys=removed,
            )
        )

    return ConfigPlan(config_path=path, scope=scope, files=files)


def _expected_for_plan(plan: ConfigPlan, expected: Mapping[Path, str]) -> None:
    for item in plan.files:
        if item.path not in expected:
            raise ConfigError("expected_hash_required: " + str(item.path))
        supplied = expected[item.path].lower()
        # Compare both the planned snapshot and the live bytes. Without the
        # second read, an owner edit between plan and apply would be silently
        # overwritten even when the caller supplied the old expected hash.
        if supplied != item.before_hash:
            raise ConfigError("hash_drift: " + str(item.path))
        current_bytes, _, current_exists = _read_state(item.path)
        current_hash = _before_hash(current_bytes, current_exists)
        if supplied != current_hash:
            raise ConfigError("hash_drift: " + str(item.path))


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return path.with_name(path.name + ".caps-backup-" + stamp)


def _atomic_write(path: Path, payload: bytes, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="." + path.name + ".", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        try:
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            directory_fd = -1
        if directory_fd >= 0:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def apply_plan(plan: ConfigPlan, expected_hashes: Mapping[Path, str]) -> Dict[str, Any]:
    """Apply a plan after preflighting every expected hash."""

    _expected_for_plan(plan, expected_hashes)
    changed = [item for item in plan.files if item.changed]
    if not changed:
        return {
            "status": "no_changes",
            "applied": False,
            "config_path": str(plan.config_path),
            "before_hash": plan.primary.before_hash,
            "after_hashes": {str(item.path): item.before_hash for item in plan.files},
            "backups": [],
        }

    backups: Dict[Path, Optional[Path]] = {}
    modes: Dict[Path, int] = {}
    written: List[FilePlan] = []
    try:
        # Make all backups before the first replacement, so an apply failure
        # has a complete rollback source.
        for item in changed:
            if item.before_exists:
                backup = _backup_path(item.path)
                backup.parent.mkdir(parents=True, exist_ok=True)
                with backup.open("xb") as handle:
                    handle.write(item.before_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    modes[item.path] = stat.S_IMODE(item.path.stat().st_mode)
                    os.chmod(backup, modes[item.path])
                except OSError:
                    pass
                backups[item.path] = backup
            else:
                backups[item.path] = None

        for item in changed:
            # Recheck after backup creation and immediately before this write.
            # A later target may have changed while earlier files were applied.
            current_bytes, _, current_exists = _read_state(item.path)
            if _before_hash(current_bytes, current_exists) != item.before_hash:
                raise ConfigError("hash_drift: " + str(item.path))
            _atomic_write(item.path, item.proposed_bytes, modes.get(item.path))
            written.append(item)
            if not item.path.exists() or sha256_file(item.path) != item.proposed_hash:
                raise ConfigError("post_write_hash_mismatch: " + str(item.path))
    except Exception as error:
        # Roll back only files that still contain the exact proposed bytes. If
        # an external process changed one during recovery, fail closed.
        rollback_error: Optional[Exception] = None
        for item in reversed(written):
            try:
                if not item.path.exists() or sha256_file(item.path) != item.proposed_hash:
                    raise ConfigError("rollback_refused_drift: " + str(item.path))
                backup = backups[item.path]
                if backup is None:
                    item.path.unlink()
                else:
                    _atomic_write(item.path, backup.read_bytes(), modes.get(item.path))
            except Exception as rollback_failure:
                rollback_error = rollback_failure
                break
        if rollback_error is not None:
            raise ConfigError("apply_failed_rollback_failed") from rollback_error
        if isinstance(error, ConfigError):
            raise
        raise ConfigError("apply_failed") from error

    return {
        "status": "applied",
        "applied": True,
        "config_path": str(plan.config_path),
        "before_hash": plan.primary.before_hash,
        "after_hashes": {str(item.path): item.proposed_hash for item in plan.files},
        "backups": [str(value) for value in backups.values() if value is not None],
    }


def rollback_file(path: Path, backup: Path, expected_hash: str) -> Dict[str, Any]:
    """Restore one backup only when the live file still matches the hash gate."""

    path = path.expanduser().resolve()
    backup = backup.expanduser().resolve()
    current_bytes, _, exists = _read_state(path)
    actual = _before_hash(current_bytes, exists)
    if expected_hash.lower() != actual:
        raise ConfigError("hash_drift: " + str(path))
    if not backup.is_file():
        raise ConfigError("backup_missing")
    payload = backup.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError("backup_not_utf8") from error
    parse_toml(text, backup)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    _atomic_write(path, payload, mode)
    restored_hash = sha256_file(path)
    if restored_hash != sha256_bytes(payload):
        raise ConfigError("rollback_post_write_hash_mismatch")
    return {
        "status": "rolled_back",
        "applied": True,
        "config_path": str(path),
        "restored_hash": restored_hash,
        "backup": str(backup),
    }


def resolve_config_path(
    *,
    project: Optional[Path] = None,
    config: Optional[Path] = None,
    scope: str = "project",
) -> Path:
    if config is not None:
        return config.expanduser().resolve()
    if scope not in {"project", "global"}:
        raise ConfigError("invalid_config_scope")
    if scope == "global":
        # An explicit global target is a CODEX_HOME directory. In particular,
        # do not append .codex when the caller already supplied CODEX_HOME.
        base = project or (
            Path(os.environ["CODEX_HOME"])
            if os.environ.get("CODEX_HOME")
            else Path.home() / ".codex"
        )
        return base.expanduser().resolve() / "config.toml"
    base = project or Path.cwd()
    return base.expanduser().resolve() / ".codex" / "config.toml"


def _expected_hash_args(values: Sequence[str], plan: ConfigPlan) -> Dict[Path, str]:
    if not values:
        raise ConfigError("expected_hash_required")
    result: Dict[Path, str] = {}
    plan_paths = {item.path for item in plan.files}
    for raw in values:
        if "=" in raw:
            raw_path, supplied = raw.rsplit("=", 1)
            target = Path(raw_path).expanduser().resolve()
        else:
            if len(plan.files) != 1:
                raise ConfigError("expected_hash_path_required")
            target = plan.primary.path
            supplied = raw
        supplied = supplied.lower()
        if supplied != MISSING_HASH and not re.fullmatch(r"[0-9a-f]{64}", supplied):
            raise ConfigError("invalid_expected_hash")
        if target not in plan_paths:
            raise ConfigError("expected_hash_path_not_in_plan")
        result[target] = supplied
    return result


def _format_text(payload: Dict[str, Any], *, include_proposed: bool = False) -> str:
    lines = [
        "Codex config plan (not applied)",
        "Scope: " + str(payload.get("scope", "explicit")),
        "Path: " + str(payload.get("config_path", "")),
        "Before hash: " + str(payload.get("before_hash", MISSING_HASH)),
        "",
        "Exact diff:",
        str(payload.get("diff", "")),
    ]
    if include_proposed:
        lines.extend(("", "Proposed text:", str(payload.get("proposed_text", ""))))
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", type=Path, help="Project directory (default: current directory)."
    )
    parser.add_argument("--config", type=Path, help="Explicit config.toml path.")
    parser.add_argument(
        "--scope",
        "--config-scope",
        choices=("project", "global"),
        default="project",
        help="Resolve project/.codex/config.toml or CODEX_HOME/config.toml.",
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument(
        "--include-proposed",
        action="store_true",
        help="Include the redacted candidate text in plan output (omitted by default).",
    )
    parser.add_argument(
        "--add-missing",
        action="store_true",
        help="Explicitly add only missing managed defaults to a valid existing config.",
    )
    parser.add_argument("--replace", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument(
        "--remove-stale-specialist",
        "--remove-specialist",
        action="append",
        default=[],
        metavar="ROLE",
        help="Remove only model/model_reasoning_effort from an inline specialist role.",
    )
    parser.add_argument(
        "--specialist-config",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="Also plan stale model/effort removal from this standalone role file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Emit a read-only exact plan.")
    apply_parser = sub.add_parser("apply", help="Apply after an explicit expected hash check.")
    apply_parser.add_argument(
        "--expected-hash",
        action="append",
        default=[],
        metavar="HASH|PATH=HASH",
        help="Required SHA-256 before hash; use 'missing' for a new file.",
    )
    rollback_parser = sub.add_parser("rollback", help="Restore a backup with a current hash gate.")
    rollback_parser.add_argument("--backup", type=Path, required=True)
    rollback_parser.add_argument("--expected-hash", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config_path = resolve_config_path(
            project=args.project, config=args.config, scope=args.scope
        )
        if args.command == "rollback":
            result = rollback_file(config_path, args.backup, args.expected_hash)
        else:
            replacements = [parse_replacement(item) for item in args.replace]
            plan = plan_config(
                config_path,
                scope=args.scope,
                replacements=replacements,
                remove_specialists=args.remove_stale_specialist,
                specialist_configs=args.specialist_config,
                add_missing=args.add_missing,
            )
            if args.command == "plan":
                result = plan.as_dict(
                    redact=True, include_proposed=args.include_proposed
                )
            else:
                expected = _expected_hash_args(args.expected_hash, plan)
                result = apply_plan(plan, expected)
        if args.format == "text" and args.command == "plan":
            print(_format_text(result, include_proposed=args.include_proposed))
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ConfigError, OSError, ValueError) as error:
        print("codex-config error: " + str(error), file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
