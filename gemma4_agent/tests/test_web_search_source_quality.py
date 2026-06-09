from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.tools_pkg.tools import ToolRegistry


class WebSearchSourceQualityTest(unittest.TestCase):
    def test_discussion_results_are_marked_and_not_primary(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_web_quality_"))
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap")
        fake_results = [
            {
                "title": "Joker (character) - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Joker_(character)",
                "snippet": "The Joker is a supervillain appearing in American comic books.",
            },
            {
                "title": "What is Joker's true origin?",
                "url": "https://www.reddit.com/r/batman/comments/x/joker_origin/",
                "snippet": "A fan theory says his real name is Arthur Fleck.",
            },
            {
                "title": "Joker | Batman Wiki",
                "url": "https://batman.fandom.com/wiki/Joker",
                "snippet": "The Joker is a supervillain and the archenemy of Batman.",
            },
        ]
        with mock.patch(
            "gemma4_agent.tools_pkg.tools._web_search_provider",
            return_value=("fake", fake_results),
        ):
            result = reg.web_search({"query": "who is the joker", "limit": 3})

        self.assertEqual(result["results"][1]["source_kind"], "discussion")
        self.assertIn("source_warning", result["results"][1])
        primary_urls = [item["url"] for item in result["primary_results"]]
        self.assertIn("https://en.wikipedia.org/wiki/Joker_(character)", primary_urls)
        self.assertIn("https://batman.fandom.com/wiki/Joker", primary_urls)
        self.assertNotIn("https://www.reddit.com/r/batman/comments/x/joker_origin/", primary_urls)
        self.assertIn("prefer primary_results", result["answer_guidance"])

    def test_research_reads_non_discussion_sources_first(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_web_quality_"))
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap")
        search_results = [
            {
                "title": "Reddit thread",
                "url": "https://www.reddit.com/r/batman/comments/x/enemy/",
                "snippet": "Fans debate Batman's enemy.",
                "source_kind": "discussion",
            },
            {
                "title": "Batman - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Batman",
                "snippet": "Batman is a DC Comics superhero.",
                "source_kind": "reference",
            },
            {
                "title": "Joker | Batman Wiki",
                "url": "https://batman.fandom.com/wiki/Joker",
                "snippet": "The Joker is Batman's archenemy.",
                "source_kind": "reference",
            },
        ]
        read_urls: list[str] = []
        reg.web_search = lambda _a: {"ok": True, "results": search_results}  # type: ignore[assignment]
        reg.web_read = lambda a: (  # type: ignore[assignment]
            read_urls.append(a["url"]),
            {"ok": True, "url": a["url"], "title": "x", "text": "excerpt"},
        )[1]

        result = reg.web_research({"query": "batman's greatest enemy", "read_limit": 2})

        self.assertTrue(result["ok"])
        self.assertEqual(read_urls, [
            "https://en.wikipedia.org/wiki/Batman",
            "https://batman.fandom.com/wiki/Joker",
        ])

    def test_web_read_with_query_redirects_to_research(self):
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_web_quality_"))
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "cap")
        calls: list[dict] = []
        reg.web_research = lambda a: (  # type: ignore[assignment]
            calls.append(dict(a)),
            {"ok": True, "status": "done", "completion_status": "research_sources_read"},
        )[1]

        result = reg.t_web({"action": "read", "query": "Batman's greatest enemy"})

        self.assertTrue(result["ok"])
        self.assertEqual(result.get("redirected_from"), "web.read")
        self.assertEqual(calls[0]["query"], "Batman's greatest enemy")


if __name__ == "__main__":
    unittest.main()
