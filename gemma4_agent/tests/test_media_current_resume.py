from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gemma4_agent.agent_core.agent import Gemma4Agent, ToolEvent
from gemma4_agent import domain_tools as dt
from gemma4_agent.infra.config import AgentConfig


def _paused_video() -> dict:
    return {
        "ok": True,
        "has_session": True,
        "title": "Kai Cenat stream",
        "artist": "",
        "source_app": "Chrome",
        "playback_status": "Paused",
        "playback_type": "Video",
        "controls": {"play": True, "pause": False},
        "verified": True,
    }


def _playing_video() -> dict:
    now = _paused_video()
    now["playback_status"] = "Playing"
    now["controls"] = {"play": False, "pause": True}
    return now


class _Executor:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, name: str, args: dict) -> dict:
        self.calls.append((name, args))
        if name == "audio":
            return {"ok": True, "status": "dispatched", "verified": None}
        if name == "browser":
            return {"ok": True, "status": "dispatched", **args}
        return {"ok": True, "status": "done"}


class CurrentVideoResumeTest(unittest.TestCase):
    def test_generic_youtube_play_resumes_paused_current_video(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "play", "provider": "youtube",
                 "query": "el ultimo video que vi"},
                executor,
            )

        self.assertEqual(result.get("completion_status"), "resumed_current_media")
        self.assertEqual(executor.calls, [("audio", {"action": "media_play_pause"})])
        self.assertEqual(result.get("now_playing", {}).get("playback_status"), "Paused")

    def test_user_deictic_text_wins_over_llm_filled_title_query(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "play", "provider": "youtube",
                 "query": "Kai Cenat stream",
                 "_user_text": "Si. Reproduce el video."},
                executor,
            )

        self.assertEqual(result.get("completion_status"), "resumed_current_media")
        self.assertEqual(executor.calls, [("audio", {"action": "media_play_pause"})])

    def test_generic_youtube_play_noops_when_current_video_already_playing(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_playing_video()):
            result = dt.media_tool(
                {"action": "play", "provider": "youtube",
                 "query": "reproduce el video"},
                executor,
            )

        self.assertEqual(result.get("completion_status"), "current_media_already_playing")
        self.assertEqual(executor.calls, [])

    def test_explicit_youtube_query_still_opens_search(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing") as now:
            result = dt.media_tool(
                {"action": "play", "provider": "youtube",
                 "query": "video de gatos"},
                executor,
            )

        now.assert_not_called()
        self.assertEqual(executor.calls, [
            ("browser", {"action": "youtube_play", "query": "video de gatos"})
        ])
        self.assertEqual(result.get("action"), "youtube_play")

    def test_media_status_with_target_includes_now_playing(self):
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "status", "app": "youtube", "query": "que estoy viendo"},
                MagicMock(),
            )

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("now_playing", {}).get("title"), "Kai Cenat stream")

    def test_media_status_from_resume_request_resumes_same_turn(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "status", "provider": "youtube",
                 "_user_text": "Si. Reproduce el video."},
                executor,
            )

        self.assertEqual(result.get("completion_status"), "resumed_current_media")
        self.assertEqual(result.get("redirected_from"), "media.status")
        self.assertEqual(executor.calls, [("audio", {"action": "media_play_pause"})])

    def test_media_status_question_does_not_resume(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "status", "provider": "youtube",
                 "_user_text": "Que video estoy viendo?"},
                executor,
            )

        self.assertTrue(result.get("ok"))
        self.assertIn("now_playing", result)
        self.assertEqual(executor.calls, [])

    def test_lo_que_estaba_viendo_is_resume_not_status_question(self):
        self.assertTrue(
            dt._looks_like_current_video_resume_request(
                "Dale, reanuda lo que estaba viendo."
            )
        )
        self.assertFalse(
            dt._looks_like_current_video_resume_request(
                "Que video estoy viendo?"
            )
        )

    def test_media_resume_uses_current_video_state_for_deictic_request(self):
        executor = _Executor()
        with patch.object(dt, "_media_now_playing", return_value=_paused_video()):
            result = dt.media_tool(
                {"action": "resume", "provider": "youtube",
                 "_user_text": "Dale, reanuda lo que estaba viendo."},
                executor,
            )

        self.assertEqual(result.get("completion_status"), "resumed_current_media")
        self.assertEqual(result.get("redirected_from"), "media.resume")
        self.assertEqual(executor.calls, [("audio", {"action": "media_play_pause"})])

    def test_agent_backstop_uses_media_status_for_current_resume(self):
        agent = Gemma4Agent(AgentConfig.from_env())
        calls = []

        def fake_media(args):
            calls.append(dict(args))
            return {
                "ok": True,
                "status": "dispatched",
                "completion_status": "resumed_current_media",
                "verified": None,
            }

        agent.tools._impls["media"] = fake_media
        event = agent._deterministic_media_resume("Continua el video.")

        self.assertIsNotNone(event)
        self.assertEqual(event.name, "media")
        self.assertEqual(calls, [{"action": "status", "provider": "youtube"}])
        self.assertIsNone(agent._deterministic_media_resume("Que video estoy viendo?"))

    def test_action_reply_description_filters_auxiliary_status_events(self):
        agent = Gemma4Agent(AgentConfig.from_env())
        events = [
            ToolEvent(
                name="safety",
                args={"action": "status"},
                result={"ok": True, "status": "done", "verified": True},
            ),
            ToolEvent(
                name="media",
                args={"action": "resume"},
                result={
                    "ok": True,
                    "status": "dispatched",
                    "verified": None,
                    "action": "resume",
                    "provider": "current_media",
                    "completion_status": "resumed_current_media",
                    "now_playing": _paused_video(),
                },
            ),
            ToolEvent(
                name="browser",
                args={"action": "active_tab_title"},
                result={"ok": True, "status": "done", "verified": True,
                        "action": "active_tab_title", "title": "Opera"},
            ),
        ]

        focused = agent._focused_events_for_action_reply(events)
        self.assertEqual([ev.name for ev in focused], ["media"])
        self.assertIn("current video", agent._describe_events_for_reply(events))

    def test_media_status_reply_repair_uses_now_playing_title(self):
        agent = Gemma4Agent(AgentConfig.from_env())
        seen = {}

        def fake_observation(user_text, evidence, fallback, target_lang=None):
            seen["user_text"] = user_text
            seen["evidence"] = evidence
            seen["target_lang"] = target_lang
            return "Estas viendo Kai Cenat stream."

        agent._llm_observation_reply = fake_observation
        events = [
            ToolEvent(
                name="media",
                args={"action": "status", "app": "youtube"},
                result={"ok": True, "status": "done", "verified": True,
                        "action": "status", "now_playing": _paused_video()},
            )
        ]

        fixed = agent._repair_media_status_reply_if_needed(
            "Que video estoy viendo en YouTube?",
            "Listo, el reproductor de YouTube esta activo.",
            events,
            "t",
        )

        self.assertEqual(fixed, "Estas viendo Kai Cenat stream.")
        self.assertEqual(seen["evidence"]["current_media_title"], "Kai Cenat stream")


if __name__ == "__main__":
    unittest.main()
