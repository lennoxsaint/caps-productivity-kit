#!/usr/bin/env python3
"""List active pinned Codex threads through the native app-server protocol.

Codex 0.147 moved pin membership behind ``threadSection/list`` and
``thread/list(sectionId=...)``. Older runtimes still support the legacy
``isPinned=true`` filter, so the helper supports both contracts while failing
closed whenever the native response cannot prove section membership.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
DEFAULT_PAGE_SIZE = 50
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PAGES = 20


class AppServerError(RuntimeError):
    """Raised when the native app-server cannot provide a valid response."""


class MethodNotFoundError(AppServerError):
    """Raised when an app-server runtime does not implement a method."""


def method_error(code: Any) -> AppServerError:
    if str(code) in {"-32600", "-32601"}:
        return MethodNotFoundError(f"app_server_method_unsupported:{code}")
    return AppServerError(f"app_server_error:{code}")


def section_list_params(cursor: str | None, page_size: int) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": page_size}
    if cursor:
        params["cursor"] = cursor
    return params


def section_thread_list_params(
    cursor: str | None, page_size: int, section_id: str
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "archived": False,
        "limit": page_size,
        "sectionId": section_id,
        "sortDirection": "desc",
        "sortKey": "updated_at",
    }
    if cursor:
        params["cursor"] = cursor
    return params


def thread_list_params(
    cursor: str | None, page_size: int, section_id: str | None = None
) -> dict[str, Any]:
    """Build legacy params, retained for 0.146 runtimes and callers."""
    params: dict[str, Any] = {
        "archived": False,
        "isPinned": True,
        "limit": page_size,
        "sortDirection": "desc",
        "sortKey": "updated_at",
        "useStateDbOnly": True,
    }
    if section_id is not None:
        return section_thread_list_params(cursor, page_size, section_id)
    if cursor:
        params["cursor"] = cursor
    return params


def status_type(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("type") or "unknown")
    if isinstance(value, str):
        return value
    return "unknown"


def project_name(cwd: str) -> str:
    if not cwd:
        return "UNKNOWN"
    name = Path(cwd).name
    return name or cwd


def redact_thread(thread: dict[str, Any]) -> dict[str, Any]:
    cwd = str(thread.get("cwd") or "")
    return {
        "thread_id": str(thread.get("id") or ""),
        "current_title": str(thread.get("name") or thread.get("title") or "Untitled"),
        "project": project_name(cwd),
        "cwd": cwd,
        "created_at": thread.get("createdAt"),
        "updated_at": thread.get("updatedAt"),
        "status": status_type(thread.get("status")),
        "is_pinned": thread.get("isPinned") is True,
    }


def page_data(result: Any, error_code: str) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(result, dict):
        raise AppServerError(error_code)
    data = result.get("data")
    if not isinstance(data, list):
        raise AppServerError(error_code)
    items = [item for item in data if isinstance(item, dict)]
    if len(items) != len(data):
        raise AppServerError(error_code)
    next_cursor = result.get("nextCursor")
    if next_cursor is not None and not isinstance(next_cursor, (str, int)):
        raise AppServerError(error_code)
    return items, str(next_cursor) if next_cursor else None


def validate_legacy_page(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise AppServerError("invalid_thread_list_data")
    threads = [item for item in data if isinstance(item, dict)]
    if len(threads) != len(data):
        raise AppServerError("invalid_thread_list_data")
    if any("isPinned" not in thread for thread in threads):
        raise AppServerError("pinned_filter_unsupported")
    if any(thread.get("isPinned") is not True for thread in threads):
        raise AppServerError("pinned_filter_not_applied")
    return threads


def validate_pinned_page(data: Any) -> list[dict[str, Any]]:
    """Backward-compatible alias for validation of a legacy pinned page."""
    return validate_legacy_page(data)


def section_value(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    if value is None and key == "id":
        value = section.get("sectionId") or section.get("section_id")
    if value is None and key == "name":
        value = section.get("title") or section.get("displayName")
    return str(value).strip() if value is not None else ""


def select_pinned_section(sections: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(sections, list) or any(not isinstance(item, dict) for item in sections):
        raise AppServerError("invalid_thread_section_data")
    candidates = [
        section
        for section in sections
        if section_value(section, "name").casefold() == "pinned"
    ]
    if not candidates:
        raise AppServerError("pinned_section_missing")
    if len(candidates) != 1:
        raise AppServerError("pinned_section_ambiguous")
    if not section_value(candidates[0], "id"):
        raise AppServerError("pinned_section_missing_id")
    return candidates[0]


def thread_section_id(thread: dict[str, Any]) -> str:
    value = thread.get("sectionId") or thread.get("section_id")
    if value is None and isinstance(thread.get("section"), dict):
        section = thread["section"]
        value = section.get("id") or section.get("sectionId") or section.get("section_id")
    return str(value).strip() if value is not None else ""


def validate_section_page(data: Any, section_id: str) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise AppServerError("invalid_thread_list_data")
    threads = [item for item in data if isinstance(item, dict)]
    if len(threads) != len(data):
        raise AppServerError("invalid_thread_list_data")
    normalized: list[dict[str, Any]] = []
    for thread in threads:
        if thread_section_id(thread) != section_id:
            raise AppServerError("section_membership_mismatch")
        copy = dict(thread)
        copy["isPinned"] = True
        normalized.append(copy)
    return normalized


def validate_section_snapshot(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not threads:
        raise AppServerError("pinned_section_empty_unverified")
    return threads


class AppServerClient:
    def __init__(self, codex_bin: str, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.process = subprocess.Popen(
            [codex_bin, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise AppServerError("app_server_stdio_unavailable")
        self._selector = selectors.DefaultSelector()
        self._selector.register(self.process.stdout, selectors.EVENT_READ)

    def close(self) -> None:
        self._selector.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)

    def send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def response(self, request_id: int) -> dict[str, Any]:
        assert self.process.stdout is not None
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            events = self._selector.select(remaining)
            if not events:
                break
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                raise AppServerError("invalid_app_server_json") from error
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message.get("error") or {}
                code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
                raise method_error(code)
            result = message.get("result")
            if not isinstance(result, dict):
                raise AppServerError("invalid_app_server_result")
            return result
        raise AppServerError("app_server_timeout")


def initialize_client(client: AppServerClient) -> None:
    client.send(
        {
            "method": "initialize",
            "id": 0,
            "params": {
                "clientInfo": {
                    "name": "caps_title_sync",
                    "title": "CAPS Pinned Title Sync",
                    "version": SCHEMA_VERSION,
                }
            },
        }
    )
    client.response(0)
    client.send({"method": "initialized", "params": {}})


def list_sections(client: AppServerClient, page_size: int) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    cursor: str | None = None
    for page in range(MAX_PAGES):
        request_id = page + 1
        client.send(
            {
                "method": "threadSection/list",
                "id": request_id,
                "params": section_list_params(cursor, page_size),
            }
        )
        result = client.response(request_id)
        page_items, next_cursor = page_data(result, "invalid_thread_section_data")
        sections.extend(page_items)
        if not next_cursor:
            return sections
        cursor = next_cursor
    raise AppServerError("thread_section_list_page_limit_exceeded")


def list_section_threads(
    client: AppServerClient, page_size: int, section_id: str
) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    for page in range(MAX_PAGES):
        request_id = page + 100
        client.send(
            {
                "method": "thread/list",
                "id": request_id,
                "params": section_thread_list_params(cursor, page_size, section_id),
            }
        )
        result = client.response(request_id)
        data, next_cursor = page_data(result, "invalid_thread_list_data")
        threads.extend(validate_section_page(data, section_id))
        if not next_cursor:
            return validate_section_snapshot(threads)
        cursor = next_cursor
    raise AppServerError("thread_list_page_limit_exceeded")


def list_legacy_pinned_threads(
    client: AppServerClient, page_size: int
) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    for page in range(MAX_PAGES):
        request_id = page + 100
        client.send(
            {
                "method": "thread/list",
                "id": request_id,
                "params": thread_list_params(cursor, page_size),
            }
        )
        result = client.response(request_id)
        data, next_cursor = page_data(result, "invalid_thread_list_data")
        threads.extend(validate_legacy_page(data))
        if not next_cursor:
            return threads
        cursor = next_cursor
    raise AppServerError("thread_list_page_limit_exceeded")


def list_pinned_threads(codex_bin: str, timeout_seconds: float, page_size: int) -> list[dict[str, Any]]:
    client = AppServerClient(codex_bin, timeout_seconds)
    try:
        initialize_client(client)
        try:
            section = select_pinned_section(list_sections(client, page_size))
        except MethodNotFoundError:
            return list_legacy_pinned_threads(client, page_size)
        threads = list_section_threads(client, page_size, section_value(section, "id"))
        if not threads:
            raise AppServerError("pinned_section_empty_or_unmigrated")
        return threads
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    if args.page_size < 1 or args.page_size > 50:
        parser.error("--page-size must be between 1 and 50")
    if args.timeout_seconds <= 0 or args.timeout_seconds > 30:
        parser.error("--timeout-seconds must be greater than 0 and at most 30")

    try:
        raw_threads = list_pinned_threads(args.codex_bin, args.timeout_seconds, args.page_size)
        threads = [redact_thread(thread) for thread in raw_threads]
        invalid = [thread["thread_id"] for thread in threads if not thread["thread_id"] or not thread["is_pinned"]]
        if invalid:
            raise AppServerError("invalid_pinned_thread_snapshot")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source": "codex_app_server_pinned_section",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "thread_count": len(threads),
            "threads": threads,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (AppServerError, FileNotFoundError, OSError) as error:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "failed",
                    "error_code": str(error),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
