---
name: youtube-dl
description: Download video or audio from YouTube and 1000+ sites via yt-dlp
triggers: [youtube, descargar video, download video, yt-dlp, mp4, mp3, descargar audio, descargar canción, video download]
requires: {bins: [yt-dlp]}
emoji: 📥
source: builtin
---
# YouTube / Video Download Skill

Use `yt-dlp` via run_command. Downloads to ~/Downloads by default.

## Download video (best quality)
```
yt-dlp -o "~/Downloads/%(title)s.%(ext)s" <URL>
```

## Download audio only (mp3)
```
yt-dlp -x --audio-format mp3 -o "~/Downloads/%(title)s.%(ext)s" <URL>
```

## Download specific quality
```
yt-dlp -f "bestvideo[height<=1080]+bestaudio" -o "~/Downloads/%(title)s.%(ext)s" <URL>
```

## List available formats
```
yt-dlp -F <URL>
```

## Download playlist
```
yt-dlp -o "~/Downloads/%(playlist_index)s - %(title)s.%(ext)s" <playlist_URL>
```

## Tips
- Always use run_command with args as a list: ["yt-dlp", "-x", "--audio-format", "mp3", "-o", "...", url]
- Default download folder: ~/Downloads
- Supports YouTube, Twitch, Twitter, Reddit, SoundCloud and 1000+ more sites
