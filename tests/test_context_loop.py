from __future__ import annotations

import unittest

from activity_agent.inference.llm.prompt import ocr_limit_for_requests, parse_context_requests


class TestParseContextRequests(unittest.TestCase):
    def test_empty_on_bad_json(self) -> None:
        self.assertEqual(parse_context_requests("not json"), set())

    def test_filters_unknown(self) -> None:
        raw = '{"context_requests":["full_ocr","unknown"],"rationale":"x"}'
        self.assertEqual(parse_context_requests(raw), {"full_ocr"})

    def test_both(self) -> None:
        raw = '{"context_requests":["past_verified_solutions","full_ocr"]}'
        self.assertEqual(
            parse_context_requests(raw),
            {"full_ocr", "past_verified_solutions"},
        )


class TestOcrLimit(unittest.TestCase):
    def test_full_ocr(self) -> None:
        self.assertGreater(
            ocr_limit_for_requests({"full_ocr"}),
            ocr_limit_for_requests(set()),
        )


if __name__ == "__main__":
    unittest.main()
