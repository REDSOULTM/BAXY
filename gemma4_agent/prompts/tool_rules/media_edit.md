Media-edit rule: media_edit(...) wraps ffmpeg for audio/video editing. Actions: status, probe, trim, concat, extract_audio, subtitles_extract, normalize, thumbnail, transcode.

Returns needs_dependency if ffmpeg is missing — report that to the user instead of pretending. normalize uses EBU R128 loudnorm (I=-23 LUFS, TP=-2 dB, LRA=7).

Distinct from media(...) (streaming playback / deeplinks) and from creative_local(...) (image generation). When the user wants to TRIM, NORMALIZE, EXTRACT, or TRANSCODE existing files, this is the tool.
