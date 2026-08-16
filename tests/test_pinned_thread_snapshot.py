import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "pinned-thread-snapshot.py"
SPEC = importlib.util.spec_from_file_location("pinned_thread_snapshot", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PinnedThreadSnapshotTests(unittest.TestCase):
    def test_legacy_thread_list_is_pinned_and_state_db_only(self):
        self.assertEqual(
            MODULE.thread_list_params(None, 50),
            {
                "archived": False,
                "isPinned": True,
                "limit": 50,
                "sortDirection": "desc",
                "sortKey": "updated_at",
                "useStateDbOnly": True,
            },
        )

    def test_section_list_params_support_pagination(self):
        self.assertEqual(
            MODULE.section_list_params("next-page", 20),
            {"cursor": "next-page", "limit": 20},
        )

    def test_modern_thread_list_uses_section_id_without_legacy_pin_filter(self):
        self.assertEqual(
            MODULE.section_thread_list_params("next-page", 20, "section-pinned"),
            {
                "archived": False,
                "cursor": "next-page",
                "limit": 20,
                "sectionId": "section-pinned",
                "sortDirection": "desc",
                "sortKey": "updated_at",
            },
        )

    def test_cursor_is_added_only_for_later_pages(self):
        params = MODULE.thread_list_params("next-page", 20)
        self.assertEqual(params["cursor"], "next-page")
        self.assertEqual(params["limit"], 20)

    def test_redaction_keeps_metadata_and_drops_content(self):
        redacted = MODULE.redact_thread(
            {
                "id": "thread-1",
                "name": "FIX TITLE SYNC",
                "cwd": "/Users/example/project",
                "createdAt": 10,
                "updatedAt": 20,
                "status": {"type": "idle"},
                "isPinned": True,
                "preview": "private prompt content",
                "turns": [{"items": ["private"]}],
            }
        )
        self.assertEqual(redacted["current_title"], "FIX TITLE SYNC")
        self.assertEqual(redacted["project"], "project")
        self.assertEqual(redacted["status"], "idle")
        self.assertTrue(redacted["is_pinned"])
        self.assertNotIn("preview", redacted)
        self.assertNotIn("turns", redacted)

    def test_selects_exact_single_pinned_section_case_insensitively(self):
        section = MODULE.select_pinned_section(
            [
                {"id": "other", "name": "Active"},
                {"id": "pinned", "name": "pInNeD"},
            ]
        )
        self.assertEqual(section, {"id": "pinned", "name": "pInNeD"})

    def test_missing_or_ambiguous_pinned_section_fails_closed(self):
        for sections, error in (
            ([{"id": "other", "name": "Active"}], "pinned_section_missing"),
            (
                [{"id": "a", "name": "Pinned"}, {"id": "b", "name": "PINNED"}],
                "pinned_section_ambiguous",
            ),
        ):
            with self.subTest(error=error):
                with self.assertRaisesRegex(MODULE.AppServerError, error):
                    MODULE.select_pinned_section(sections)

    def test_section_page_requires_matching_membership(self):
        normalized = MODULE.validate_section_page(
            [
                {"id": "thread-1", "sectionId": "pinned"},
                {"id": "thread-2", "section": {"id": "pinned"}},
            ],
            "pinned",
        )
        self.assertEqual([item["id"] for item in normalized], ["thread-1", "thread-2"])
        with self.assertRaisesRegex(MODULE.AppServerError, "section_membership_mismatch"):
            MODULE.validate_section_page(
                [{"id": "thread-1", "sectionId": "other"}],
                "pinned",
            )

    def test_empty_section_snapshot_fails_closed(self):
        with self.assertRaisesRegex(
            MODULE.AppServerError,
            "pinned_section_empty_unverified",
        ):
            MODULE.validate_section_snapshot([])

    def test_section_discovery_paginates_through_native_pages(self):
        class Client:
            def __init__(self):
                self.sent = []

            def send(self, message):
                self.sent.append(message)

            def response(self, request_id):
                return (
                    {"data": [{"id": "other", "name": "Active"}], "nextCursor": "next"}
                    if request_id == 1
                    else {"data": [{"id": "pinned", "name": "Pinned"}], "nextCursor": None}
                )

        client = Client()
        sections = MODULE.list_sections(client, 50)
        self.assertEqual([item["id"] for item in sections], ["other", "pinned"])
        self.assertEqual(client.sent[1]["params"]["cursor"], "next")

    def test_method_not_found_is_distinguishable_for_legacy_fallback(self):
        for code in (-32601, -32600):
            with self.subTest(code=code):
                error = MODULE.method_error(code)
                self.assertIsInstance(error, MODULE.MethodNotFoundError)

    def test_legacy_page_still_requires_pin_metadata(self):
        with self.assertRaisesRegex(MODULE.AppServerError, "pinned_filter_unsupported"):
            MODULE.validate_legacy_page([{"id": "thread-1"}])

    def test_page_without_pin_metadata_fails_before_pagination_continues(self):
        with self.assertRaisesRegex(
            MODULE.AppServerError,
            "pinned_filter_unsupported",
        ):
            MODULE.validate_pinned_page(
                [{"id": "thread-1", "name": "Missing pin metadata"}]
            )

    def test_page_rejects_an_unpinned_result_from_a_pinned_query(self):
        with self.assertRaisesRegex(
            MODULE.AppServerError,
            "pinned_filter_not_applied",
        ):
            MODULE.validate_pinned_page(
                [{"id": "thread-1", "isPinned": False}]
            )


if __name__ == "__main__":
    unittest.main()
