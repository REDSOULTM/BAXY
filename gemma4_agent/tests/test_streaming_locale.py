"""Tests for F-009: streaming web URL must support locale override
(Disney+ hardcoded /es-419/ rompe si el user esta en otra region).
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from gemma4_agent.domain_tools import (
    _STREAMING_PLATFORMS,
    _resolve_streaming_web_url,
)


class TestResolveStreamingWebUrl(unittest.TestCase):

    def test_disney_default_locale_es_419(self):
        spec = _STREAMING_PLATFORMS["disney"]
        url = _resolve_streaming_web_url(spec, state=None)
        self.assertEqual(url, "https://www.disneyplus.com/es-419/browse/search")

    def test_disney_with_user_locale_es_es(self):
        spec = _STREAMING_PLATFORMS["disney"]
        # state with user_locale attribute
        state = SimpleNamespace(user_locale="es-es")
        url = _resolve_streaming_web_url(spec, state=state)
        self.assertEqual(url, "https://www.disneyplus.com/es-es/browse/search")

    def test_disney_with_user_locale_en_us(self):
        spec = _STREAMING_PLATFORMS["disney"]
        state = SimpleNamespace(user_locale="en-us")
        url = _resolve_streaming_web_url(spec, state=state)
        self.assertEqual(url, "https://www.disneyplus.com/en-us/browse/search")

    def test_disney_with_empty_user_locale_falls_back_to_default(self):
        spec = _STREAMING_PLATFORMS["disney"]
        state = SimpleNamespace(user_locale="   ")
        url = _resolve_streaming_web_url(spec, state=state)
        self.assertEqual(url, "https://www.disneyplus.com/es-419/browse/search")

    def test_platform_without_template_falls_back_to_web_url(self):
        # Spotify spec uses static web_url (no template).
        spec = _STREAMING_PLATFORMS["spotify"]
        url = _resolve_streaming_web_url(spec, state=None)
        self.assertEqual(url, str(spec.get("web_url")))


if __name__ == "__main__":
    unittest.main()
