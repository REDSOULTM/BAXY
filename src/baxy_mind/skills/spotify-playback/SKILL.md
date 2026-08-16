---
name: spotify-playback
description: Play an exact Spotify title in an authenticated session and optionally adjust system audio.
operations:
  - media.play.exact
  - media.control
  - audio.volume
priority: 90
---
# Spotify playback

For a named song use one `media.play.exact` step with `provider=spotify` and the
literal title. This operation owns opening or selecting the authenticated
Spotify session; do not add `app.open` when Spotify is not a supported app enum.
Require now-playing evidence for the exact result. Use `media.control` only for
explicit play/pause/next/previous/stop requests. `audio.volume` is independent
and may run after playback when the objective gives a literal level.

If the user asks to play an exact title and then pause it, use
`media.play.exact` once followed by `media.control(action=pause)` once. Pausing
is never a second exact-selection step.

Exact selection may use an authenticated Spotify Web API session; select the
highest-ranked exact folded title and verify the returned track ID through
currently-playing. Without API authority, SMTC may resume only an already
matching title and must not pretend it selected a different track.
