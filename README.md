# 🎤 VoicePaste

Voice-to-text application with real-time transcription and automatic clipboard integration.

**Press Shift+V, speak, press Shift+V again - your text is ready to paste.** ✨

## ✨ Features

- 🎯 **One-key activation** - Simple Shift+V hotkey to start/stop recording
- ⚡ **Real-time transcription** - Using OpenAI Whisper Turbo model
- 🚀 **GPU acceleration** - CUDA support for fast transcription (CPU fallback available)
- 📋 **Automatic clipboard** - Transcribed text instantly available for pasting
- 🔔 **System tray integration** - Runs quietly in background
- 🧠 **Smart memory management** - Auto-loads/unloads model to save GPU memory
- 🎧 **Virtual audio support** - Works with NVIDIA Broadcast, VB-Cable, Krisp, etc.
- 🌍 **Cross-platform** - Windows, Linux, macOS

## 🚀 Quick Start

### 🪟 Windows (with NVIDIA GPU)

```bash
python --version  # Must be 3.12 (not 3.13!)
python -m venv .venv
.venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper pynput PyAudio scipy pyperclip pystray pytest pytest-asyncio
python main.py
```

### 🐧 Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper pynput PyAudio scipy pyperclip pystray pytest pytest-asyncio
python main.py
```

### 💻 CPU-only (no GPU)

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

Press `Shift+V` → 🎤 speak → press `Shift+V` again → ✅ text ready in clipboard!

## 📋 Requirements

- 🐍 **Python 3.12** (not 3.13 - PyTorch CUDA wheels not yet available for 3.13)
- 🎮 NVIDIA GPU with CUDA (optional - runs on CPU without GPU)
- 🎤 Microphone

## 📦 Installation

### 1️⃣ Check Python version

```bash
python --version
```

If you have Python 3.13, install Python 3.12 from python.org

### 2️⃣ Clone repository

```bash
git clone https://github.com/yourusername/VoicePaste.git
cd VoicePaste
```

### 3️⃣ Create virtual environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 4️⃣ Install dependencies

**With GPU (NVIDIA CUDA):** 🎮
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper pynput PyAudio scipy pyperclip pystray pytest pytest-asyncio
```

**Without GPU (CPU only):** 💻
```bash
pip install -r requirements.txt
```

### 5️⃣ Verify CUDA (optional)

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

✅ If output is `CUDA: True` - you have GPU support
❌ If `False` - will run on CPU (slower but works)

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
- Right-click tray icon → Quit

## 🔄 How it works

1. 🚀 Start application - tray icon appears in system tray
2. ⌨️ Press `Shift+V` - recording starts (icon turns red)
3. 🎤 Speak into microphone
4. ⌨️ Press `Shift+V` again - recording stops
5. ⏳ Wait for transcription (icon turns orange)
6. 📋 Text automatically copied to clipboard
7. ✨ Paste anywhere with `Ctrl+V`

**Icon colors:** 🟢 ready → 🔴 recording → 🟠 processing → 🟢 ready

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

## 📁 Project Structure

```
VoicePaste/
├── src/
│   ├── 🎤 audio_recorder.py       - Audio recording from microphone
│   ├── 🤖 transcriber.py          - Whisper transcription
│   ├── 📋 clipboard_manager.py    - Clipboard management
│   ├── ⌨️ hotkey_handler.py       - Global hotkey handling
│   ├── 🔔 tray_icon.py            - System tray integration
│   └── 🎯 voice_paste_app.py      - Main application
├── 🧪 tests/                      - Unit tests
├── 🚀 main.py                     - Entry point
└── 📦 requirements.txt            - Dependencies
```

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

### 📦 PyAudio installation fails
**Windows:** Download wheel from [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio python3-tk
pip install PyAudio
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install portaudio-devel
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

## 🛠️ Development

### 🧪 Running tests
```bash
pytest tests/
```

### 📐 Code structure
- 🧩 Each module is self-contained and testable
- 🔄 Threading used for non-blocking operations
- ⚡ Lazy loading for optimal memory usage

## 🤝 Contributing

Contributions welcome! Please:
1. 🍴 Fork the repository
2. 🌿 Create a feature branch
3. ✏️ Make your changes
4. ✅ Add tests if applicable
5. 📬 Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Credits

- **Whisper** - OpenAI's speech recognition model
- **faster-whisper** - Efficient Whisper implementation by Guillaume Klein
- Built with Python, PyTorch, and lots of ☕

## 👨‍💻 Author

Created by dam2452
