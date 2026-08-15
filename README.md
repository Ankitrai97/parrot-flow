# Parrot Flow

Parrot Flow is a local-first Windows dictation app. Press `Ctrl+Space` to start and stop recording; the final transcript is typed into the app you were using. Speech recognition runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), so your audio is not sent to a cloud transcription service.

![License](https://img.shields.io/badge/license-MIT-8b5cf6)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0ea5e9)

## Features

- Local GPU-accelerated transcription with NVIDIA CUDA, plus CPU fallback.
- Global `Ctrl+Space` hotkey and a draggable floating Parrot Flow control.
- Start, stop, and cancel controls that preserve the target app for text insertion.
- Compact modern UI with a Parrot Flow avatar and live recording state.
- Optional Windows sign-in startup.
- No clipboard replacement and no cloud audio upload.

## Download and install

When a packaged release is available, download `ParrotFlow.zip` from the repository's **Releases** page, extract it, and run `ParrotFlow.exe`. Windows may show a SmartScreen prompt for an unsigned open-source build; inspect the repository and choose **More info → Run anyway** only if you trust the release.

The first dictation downloads the selected Whisper model and caches it locally. Keep the app running; click **X** only to hide the floating control. Press `Ctrl+Space` to show it again.

## GPU support

Parrot Flow defaults to CUDA with FP16 on supported NVIDIA GPUs. The `small` Whisper model is a good balance for an RTX 3050 with 6 GB of VRAM. If CUDA is unavailable, the app temporarily falls back to CPU so dictation remains usable.

The packaged build includes the CUDA runtime libraries, but users still need a current NVIDIA graphics driver. On machines without a supported NVIDIA GPU, use CPU mode:

```toml
# %APPDATA%\LocalDictate\config.toml
device = "cpu"
compute_type = "int8"
```

## Run from source

Requirements: Windows 10/11, Python 3.11+, a microphone, and optionally an NVIDIA GPU.

```powershell
git clone https://github.com/Ankitrai97/parrot-flow.git
cd parrot-flow
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[gpu,dev]"
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m localdictate
```

To start it automatically when you sign in:

```powershell
& .\.venv\Scripts\python.exe -m localdictate --install-startup
```

Use `--remove-startup` to remove that entry later.

## Build a Windows release

From an activated development setup:

```powershell
.\packaging\build_windows.ps1
```

The application is created at `dist\ParrotFlow\ParrotFlow.exe`. Zip the entire `dist\ParrotFlow` folder—do not distribute the `.exe` by itself.

## Configuration

Parrot Flow stores its configuration at `%APPDATA%\LocalDictate\config.toml`. Useful options include:

```toml
hotkey = "ctrl+space"
model = "small"
device = "cuda"
compute_type = "float16"
```

## Privacy

Parrot Flow records only while you activate it and processes audio locally. Audio is held in memory for transcription and is not written to disk by the app. The first use of each Whisper model downloads its model files from Hugging Face.

## Contributing

Contributions and bug reports are welcome. Please run the test suite before opening a pull request:

```powershell
& .\.venv\Scripts\python.exe -m pytest
```

## License

Parrot Flow is released under the [MIT License](LICENSE).
