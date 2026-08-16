audio(...) = system master volume + media keys. Actions: get_volume, set_volume, mute, devices, set_default, media_play_pause, media_stop, next, previous.

set_volume(level: int 0-100) = ABSOLUTE percentage — resolve number-words ("ten"/"veinte") to int BEFORE passing. Relative changes ("a bit louder") = compute against a prior get_volume.

mute(state: bool): state=true SILENCES (mute); state=false RESTORES (unmute). "silenciá/mute/coupe le son/stumm" -> mute(state=true); "activá el sonido/unmute/desmuteá/rétablis le son/reactiva o som" -> mute(state=false). Default state=true. This is the ONLY way to unmute (no separate unmute action).

NOT FOR: output device routing -> action='set_default' on a device id from action='devices'. NOT FOR closing/stopping a media app — media_stop sends a global media key; to close the player use window(action='close') or app(action='close'). For ambiguous "stop the music", the intent_validator may require an <intent> tag (audio↔media↔window↔app).
