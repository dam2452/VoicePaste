# 🎤 VoicePaste
<img width="386" height="385" alt="logo" src="https://github.com/user-attachments/assets/ea7bd00f-d363-4f51-9146-c9e5712f0860" />

Voice-to-text application with real-time transcription and automatic clipboard integration.

**Press Shift+V, speak, press Shift+V again - your text is ready to paste.** ✨

## ✨ Features

- 🎯 **Voice recording** - Simple Shift+V hotkey to start/stop recording
- 📺 **YouTube transcription** - Press Shift+Y to transcribe YouTube videos from clipboard
- 📁 **Local file transcription** - Press Shift+F to transcribe audio/video files from clipboard
- ⚡ **Real-time transcription** - Using OpenAI Whisper Turbo model
- 🚀 **GPU acceleration** - CUDA support for fast transcription (CPU fallback available)
- 📋 **Automatic clipboard** - Transcribed text instantly available for pasting
- 💾 **Smart caching** - YouTube and file transcriptions cached for 1 hour (avoid re-processing)
- 🔔 **System tray integration** - Runs quietly in background with functional menu
- 🧠 **Smart memory management** - Auto-loads/unloads model to save GPU memory
- 🎧 **Virtual audio support** - Works with NVIDIA Broadcast, VB-Cable, Krisp, etc.
- 🌍 **Cross-platform** - Windows, Linux, macOS

## 🚀 Quick Start

> **⭐ Recommended:** Windows with NVIDIA GPU for best performance

### 🪟 Windows

```bash
# Check Python version (must be 3.12)
python --version

# Install FFmpeg
winget install ffmpeg

# Setup project
git clone https://github.com/yourusername/VoicePaste.git
cd VoicePaste
python -m venv .venv
.venv\Scripts\activate

# Install dependencies (with CUDA for GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# Run
python main.py
```

### 🐧 Linux

```bash
# Check Python version (must be 3.12)
python3.12 --version

# Install system dependencies
sudo apt update && sudo apt install ffmpeg portaudio19-dev python3-tk

# Setup project
git clone https://github.com/yourusername/VoicePaste.git
cd VoicePaste
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# Run
python main.py
```

### 🍎 macOS

```bash
# Check Python version (must be 3.12)
python3.12 --version

# Install system dependencies
brew install ffmpeg portaudio

# Setup project
git clone https://github.com/yourusername/VoicePaste.git
cd VoicePaste
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

---

**Usage:**
- Press `Shift+V` → speak → press `Shift+V` → text in clipboard ✅
- Copy YouTube URL → press `Shift+Y` → video transcribed → text in clipboard ✅
- Copy file or file path → press `Shift+F` → file transcribed → text in clipboard ✅

## 🎯 Usage

### Basic
```bash
python main.py
```

### 🎤 Select microphone
List available devices:
```bash
python main.py --list-devices
```

Use specific device:
```bash
python main.py --device 6
```

### 🚀 Keep model in memory
```bash
python main.py --keep-model-loaded
```

### 🚪 Exit
- Press `Ctrl+C` in terminal
- Right-click tray icon → Exit

## 🔄 How it works

### 🎤 Voice Recording

1. 🚀 Start application - tray icon appears in system tray
2. ⌨️ Press `Shift+V` - recording starts (icon turns red)
3. 🎤 Speak into microphone
4. ⌨️ Press `Shift+V` again - recording stops
5. ⏳ Wait for transcription (icon turns orange)
6. 📋 Text automatically copied to clipboard
7. ✨ Paste anywhere with `Ctrl+V`

### 📺 YouTube Transcription

1. 📋 Copy YouTube video URL to clipboard
2. ⌨️ Press `Shift+Y` - downloading starts (icon turns purple)
3. ⏳ Wait for download and transcription (icon shows download arrow)
4. 📝 Transcription automatically copied to clipboard
5. ✨ Paste anywhere with `Ctrl+V`
6. 💾 Transcription cached for 1 hour - next use instant!

### 📁 Local File Transcription

1. 📋 Copy file from File Explorer (Ctrl+C on file) OR copy file path as text
2. ⌨️ Press `Shift+F` - processing starts (icon turns orange)
3. ⏳ Wait for audio extraction and transcription
4. 📝 Transcription automatically copied to clipboard
5. ✨ Paste anywhere with `Ctrl+V`
6. 💾 Transcription cached for 1 hour - next use instant!

**Supported formats:**
- Audio: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`, `.wma`
- Video: `.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`

**Icon colors:** 🟢 ready → 🔴 recording → 🟣 downloading → 🔵 processing → 🟢 ready

## 🎛️ Advanced Features

### 🧠 Smart Memory Management

Application uses intelligent 3-tier memory management by default:
- ⚡ **Preloading**: Model starts loading to VRAM when you start recording - ready by the time you finish speaking
- 🎮 **VRAM (GPU)**: Model actively used on CUDA for transcription
- 💾 **RAM (CPU)**: After **1 hour** of inactivity, model moves from VRAM to RAM
- 💤 **Disk**: After **5 hours** of inactivity, model fully unloaded from memory
- 🔄 **Auto-recovery**: Model automatically moves back to GPU when needed

Use `--keep-model-loaded` flag if:
- 🔁 You use the app frequently
- 💾 You have plenty of GPU memory
- ⚡ Speed is more important than memory usage

### 🎧 Audio Compatibility

Automatically adapts to your microphone:
- 🔍 Detects native sample rate (e.g. 48kHz for NVIDIA Broadcast)
- 📼 Records at native sample rate for maximum compatibility
- 🔄 Auto-resamples to 16kHz for Whisper processing
- 🎛️ Works with virtual audio devices (NVIDIA Broadcast, VB-Cable, Krisp, etc.)

## 🔧 Troubleshooting

### ⚠️ cuDNN / CUDA errors
Application automatically falls back to CPU if CUDA fails. Slower but works.

### 🎤 Microphone issues
```bash
python main.py --list-devices
python main.py --device <ID>
```

### ⏱️ "Recording too short, ignoring..."
Speak longer (minimum 1 second) or check if microphone is working.

### 🎬 FFmpeg not found (for YouTube transcription)

FFmpeg is a system dependency (not a Python package) and must be installed via system package manager.

**Windows:**
```bash
winget install ffmpeg
```

**Linux:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 📦 PyAudio installation fails

Already included in Quick Start for each OS. If still fails:

**Windows:**
```bash
pip install pipwin
pipwin install pyaudio
```

**Linux:**
```bash
sudo apt update && sudo apt install portaudio19-dev python3-tk
pip install PyAudio
```

**macOS:**
```bash
brew install portaudio
pip install PyAudio
```

### 🐧 Linux Additional Requirements
For system tray icon support:
```bash
sudo apt-get install gir1.2-appindicator3-0.1 libappindicator3-1
```

### 🍎 macOS Additional Notes
- System tray icon requires Pillow with ImageDraw support (included in requirements)
- Global hotkeys work system-wide but may require accessibility permissions
- Go to System Preferences → Security & Privacy → Privacy → Accessibility
- Add Terminal or your Python interpreter to allowed applications

## 📄 License

MIT License - see LICENSE file for details
