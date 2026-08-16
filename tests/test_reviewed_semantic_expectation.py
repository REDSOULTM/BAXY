import hashlib
import json
import unittest
from collections.abc import Iterable
from typing import Any
from unittest.mock import patch

import scripts.build_exhaustive_runtime_oracle as runtime_oracle
from scripts.build_exhaustive_runtime_oracle import (
    CASES,
    EXISTING,
    is_runtime,
    read_jsonl,
    reviewed_semantic_expectation,
)


RUNTIME_CASES = 14_845
RUNTIME_MATCHES = 4_026
RUNTIME_DIGEST = "ebcf511e32532e2d84216ec489760d9820d71e22378230a75126ded8a2fbd445"
VERSIONED_CASES = 11_087
VERSIONED_MATCHES = 2_493
VERSIONED_DIGEST = "e43a428e8b60728f78b2bce0137443db5bdf6811157e508da7bb535b65df1742"


def semantic_expectation_digest(
    rows: Iterable[dict[str, Any]],
    *,
    runtime_only: bool,
) -> tuple[int, int, str]:
    expectations: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        if runtime_only and not is_runtime(row):
            continue
        text = row.get("text_literal") or ""
        if text not in expectations:
            expectations[text] = reviewed_semantic_expectation(text)

    encoded = "".join(
        json.dumps(
            {"text": text, "result": result},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for text, result in sorted(expectations.items())
    ).encode("utf-8")
    return (
        len(expectations),
        sum(result is not None for result in expectations.values()),
        hashlib.sha256(encoded).hexdigest(),
    )


class ReviewedSemanticExpectationCharacterizationTests(unittest.TestCase):
    def test_dispatcher_stops_at_the_first_matching_reviewer(self) -> None:
        calls: list[tuple[str, str, str]] = []
        winner = {"review_rule": "first_match"}

        def miss(text: str, value: str) -> None:
            calls.append(("miss", text, value))

        def match(text: str, value: str) -> dict[str, str]:
            calls.append(("match", text, value))
            return winner

        def must_not_run(text: str, value: str) -> None:
            calls.append(("must_not_run", text, value))

        with patch.object(
            runtime_oracle,
            "ORDERED_REVIEWERS",
            (miss, match, must_not_run),
        ):
            result = runtime_oracle.reviewed_semantic_expectation("  OPEN Chrome  ")

        self.assertIs(result, winner)
        self.assertEqual(
            calls,
            [
                ("miss", "  OPEN Chrome  ", "open chrome"),
                ("match", "  OPEN Chrome  ", "open chrome"),
            ],
        )

    def test_runtime_local_semantic_digest_is_frozen(self) -> None:
        if not CASES.is_file():
            self.skipTest("The local exhaustive runtime ledger is unavailable.")

        self.assertEqual(
            semantic_expectation_digest(read_jsonl(CASES), runtime_only=True),
            (RUNTIME_CASES, RUNTIME_MATCHES, RUNTIME_DIGEST),
        )

    def test_versioned_corpus_semantic_digest_is_frozen(self) -> None:
        self.assertEqual(
            semantic_expectation_digest(read_jsonl(EXISTING), runtime_only=False),
            (VERSIONED_CASES, VERSIONED_MATCHES, VERSIONED_DIGEST),
        )

    def test_first_match_precedences_are_frozen(self) -> None:
        cases = {
            "abre Chrome y busca Carter": (
                "operation",
                ["web"],
                "explicit_browser_web_search",
            ),
            "Abre Portal desde Steam": (
                "operation",
                ["game"],
                "explicit_steam_game_launch",
            ),
            "Busca información sobre la reunión": (
                "review_required",
                [],
                "search_scope_missing",
            ),
            "what is a hard disk": (
                "none",
                [],
                "stable_definition_is_conversation",
            ),
            "y en Tokio?": (
                "review_required",
                [],
                "follow_up_requires_session_context",
            ),
            "Pues hazlo": (
                "none",
                [],
                "contextual_or_ambiguous_reference_requires_clarification",
            ),
            "abre el navegador pls": (
                "operation",
                ["app"],
                "explicit_browser_application_open",
            ),
            "navegá a youtube.com": (
                "operation",
                ["browser"],
                "explicit_public_url_navigation",
            ),
            "next": (
                "none",
                [],
                "bare_context_dependent_selector_requires_clarification",
            ),
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertIsNotNone(result)
                self.assertEqual(
                    (
                        result["expected_effect"],
                        result["families"],
                        result["review_rule"],
                    ),
                    expected,
                )

        for explicit_media_target in (
            "next track please",
            "play next one",
            "poné la siguiente canción",
        ):
            with self.subTest(text=explicit_media_target):
                result = reviewed_semantic_expectation(explicit_media_target)
                self.assertTrue(
                    result is None
                    or result.get("review_rule")
                    != "bare_context_dependent_selector_requires_clarification"
                )


if __name__ == "__main__":
    unittest.main()
