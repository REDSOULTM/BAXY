---
name: ffmpeg
description: Convert, trim, compress or extract audio from video files using ffmpeg
triggers: [ffmpeg, convertir video, convert video, comprimir video, compress video, recortar video, trim video, extraer audio, extract audio, mp4, mkv, avi, webm, gif, gif from video]
requires: {bins: [ffmpeg]}
emoji: 🎬
source: builtin
---
# FFmpeg Skill

Use ffmpeg via run_command for all video/audio processing tasks.

## Convert format
```
ffmpeg -i input.mp4 output.mkv
ffmpeg -i input.mkv -c:v libx264 -c:a aac output.mp4
```

## Trim video (start to end time)
```
ffmpeg -i input.mp4 -ss 00:00:30 -to 00:01:00 -c copy output.mp4
```

## Compress video (reduce file size)
```
ffmpeg -i input.mp4 -vcodec libx264 -crf 28 output.mp4
```
CRF: 18=high quality, 28=smaller file, 51=lowest quality

## Extract audio as mp3
```
ffmpeg -i input.mp4 -vn -acodec libmp3lame -q:a 2 output.mp3
```

## Create GIF from video
```
ffmpeg -i input.mp4 -ss 00:00:05 -t 3 -vf "fps=10,scale=480:-1" output.gif
```

## Merge video + audio
```
ffmpeg -i video.mp4 -i audio.mp3 -c:v copy -c:a aac output.mp4
```

## Tips
- Always resolve full file paths before running
- Use -y flag to overwrite output without asking: add "-y" to args list
- Default output to same folder as input unless user specifies otherwise
