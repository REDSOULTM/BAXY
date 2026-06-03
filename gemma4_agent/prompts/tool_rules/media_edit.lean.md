Media-edit: media_edit(...) = ffmpeg para audio/video. Actions: status, probe, trim, concat, extract_audio, subtitles_extract, normalize, thumbnail, transcode.

- Sin ffmpeg -> needs_dependency: reportalo, NO finjas que se hizo.
- normalize: EBU R128 loudnorm (I=-23 LUFS, TP=-2 dB, LRA=7).

Distinto de media(...) (playback/deeplinks) y creative_local(...) (gen imágenes). Para TRIM/NORMALIZE/EXTRACT/TRANSCODE de archivos existentes = este tool.
