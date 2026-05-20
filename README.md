# 🎙️ Transcriber

A desktop app that converts audio and video files to plain text using OpenAI Whisper — fully local, no internet required for transcription. Built with Python and Tkinter, styled after DaVinci Resolve.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Whisper](https://img.shields.io/badge/OpenAI-Whisper-orange?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Screenshots

<img width="1602" height="1013" alt="image" src="https://github.com/user-attachments/assets/b7fff635-a6a8-4887-8e18-11a523e9ec4b" />
<img width="1602" height="1013" alt="image" src="https://github.com/user-attachments/assets/494ca50a-24ec-42e3-bbc5-eb05590f3741" />
<img width="1602" height="1013" alt="Screenshot 2026-05-20 102934" src="https://github.com/user-attachments/assets/17471bb7-4510-4589-8342-3baf6cb30582" />
<img width="1602" height="1013" alt="Screenshot 2026-05-20 102949" src="https://github.com/user-attachments/assets/c50b7c41-64cf-4964-9062-2d2cfe302439" />



---

## Features

- 🎬 **Video & Audio support** — `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`
- 🧠 **Powered by OpenAI Whisper** — runs fully offline after the first model download
- 🌍 **Translation** — translate transcripts to 17+ languages using Google Translate
- ✏️ **Editable outputs** — edit both the transcript and translation directly in the app
- 📋 **One-click copy** — copy transcript or translation to clipboard instantly
- 🖼️ **File preview** — shows video thumbnail, file name, and size on import
- ⏱️ **Time estimate** — shows approximate transcription time based on file duration and selected model
- ⏹️ **Kill switch** — stop transcription mid-process without hanging
- 🎨 **DaVinci Resolve-inspired UI** — dark, clean, professional interface

---

## Requirements

### System
- Python **3.10 or newer**
- **ffmpeg** (required for video files only)

### Python Packages
```bash
pip install openai-whisper deep-translator Pillow
```

### Installing ffmpeg (Windows)
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html) → *Windows builds from gyan.dev*
2. Extract to `C:\FFmpeg`
3. Add `C:\FFmpeg` to your system **PATH** environment variable
4. Restart your terminal and verify with `ffmpeg -version`

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Peyush7821/AI-tools/tree/Transcriber.git

# Install dependencies
pip install openai-whisper deep-translator Pillow

# Run the app
python python_transcribe.py
```

---

## Whisper Models

Whisper models are downloaded automatically on first use. Choose based on your needs:

| Model  | Size    | Speed   | Accuracy |
|--------|---------|---------|----------|
| tiny   | ~75 MB  | Fastest | Low      |
| base   | ~145 MB | Fast    | Good     |
| small  | ~465 MB | Medium  | Better   |
| medium | ~1.5 GB | Slow    | Great    |
| large  | ~2.9 GB | Slowest | Best     |

> **Tip:** For Hindi or other non-English languages, `medium` or `large` is strongly recommended.

Models are cached at `C:\Users\<you>\.cache\whisper\` after the first download.

---

## Usage

1. Click **IMPORT** and select your audio or video file
2. Choose a **Model** and **Language** from the settings
3. Click **▶ TRANSCRIBE** and wait for it to finish
4. The transcript appears in the left panel — click **COPY ALL** to copy it
5. Optionally, select a target language and click **TRANSLATE**

---

## Translation

Translation uses [deep-translator](https://github.com/nidhaloff/deep-translator) with Google Translate under the hood. Requires an internet connection. Supports 17+ languages including Hindi, Tamil, Telugu, Arabic, and more.

---

## Tech Stack

| Library | Purpose |
|---|---|
| [openai-whisper](https://github.com/openai/whisper) | Speech-to-text transcription |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Text translation |
| [Pillow](https://python-pillow.org/) | Video thumbnail extraction |
| [tkinter](https://docs.python.org/3/library/tkinter.html) | GUI framework |
| [ffmpeg](https://ffmpeg.org/) | Audio extraction from video |

---

## Notes

- Transcription runs **entirely on your CPU** — no GPU or internet needed
- No data is sent anywhere during transcription
- Translation requires internet (Google Translate)
- The app does **not** save any files to your disk — output only lives in the window until you copy it

---

## License

MIT License — feel free to use, modify, and distribute.
