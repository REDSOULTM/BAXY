Per-app audio: to route a single app's audio ("manda solo Spotify al AUX") use audio_device(action="set_app_route", app="Spotify.exe", device="<device>", role="1"). get_app_routes lists current per-app overrides.

Audio device: for "cambia a AUX" / "usa Focusrite" / "cambia el dispositivo de audio" use audio_device(...), NOT audio(set_default). If a helper like SoundVolumeView is missing -> report needs_dependency; do NOT pretend the device changed.
