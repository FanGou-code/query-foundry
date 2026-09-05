"""Offline tests for frame query response parsing (migrated from the main repo)."""

from __future__ import annotations

import json
import unittest

from foundry.sequence import parse_frame_query_candidates


class FrameQueryParserTests(unittest.TestCase):
    def test_frame_query_parser(self):
        candidates = parse_frame_query_candidates(json.dumps({
            "query": "The pedestrian wearing a bright yellow waterproof jacket",
            "alternate_query": "The yellow coated person beside the metal railing",
            "uncertain": False,
        }))
        self.assertFalse(candidates["uncertain"])
        self.assertIn("yellow", candidates["query"])

    def test_frame_query_rejects_annotation_scaffolding(self):
        payload = {
            "query": "The person inside the red rectangle wearing a yellow jacket",
            "alternate_query": None,
            "uncertain": False,
        }
        with self.assertRaisesRegex(ValueError, "annotation scaffolding"):
            parse_frame_query_candidates(json.dumps(payload))
        payload["query"] = "The pedestrian wearing a yellow jacket in this frame"
        with self.assertRaisesRegex(ValueError, "annotation scaffolding"):
            parse_frame_query_candidates(json.dumps(payload))
        payload["query"] = "The target pedestrian wearing a yellow jacket"
        with self.assertRaisesRegex(ValueError, "annotation term"):
            parse_frame_query_candidates(json.dumps(payload))
        payload["query"] = "The blurry white thing held in the person's hand"
        with self.assertRaisesRegex(ValueError, "generic category"):
            parse_frame_query_candidates(json.dumps(payload))

    def test_parsers_reject_duplicate_json_keys(self):
        duplicate_top_level = (
            '{"query":"The person wearing a yellow waterproof jacket",'
            '"query":"The person wearing a blue waterproof jacket",'
            '"alternate_query":null,"uncertain":false}'
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_frame_query_candidates(duplicate_top_level)


if __name__ == "__main__":
    unittest.main()
