Audio rule: audio(...) controls system master volume and media keys. Actions: get_volume, set_volume, mute, devices, set_default, media_play_pause, media_stop, next, previous.

set_volume(level: int 0-100) takes an ABSOLUTE percentage — the caller MUST resolve number-words ("ten", "veinte") to ints before passing. Relative changes ("a bit louder") must be computed against a prior get_volume.

mute(state: bool) silences or restores the sound. state=true SILENCES (mute); state=false RESTORES (unmute). So "silenciá / mute / coupe le son / stumm" → mute(state=true); "activá el sonido / unmute / desmuteá / rétablis le son / ton an / reactiva o som" → mute(state=false). Default state is true. This is the ONLY way to unmute — there is no separate unmute action.

NOT FOR: changing output device routing requires action='set_default' on a device id from action='devices'. NOT FOR: closing or stopping a media app — media_stop sends a global media key; to close the player use window(action='close') or app(action='close').

For ambiguous intent like "stop the music" the intent_validator may require an <intent> tag (audio↔media↔window↔app).
