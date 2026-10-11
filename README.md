# Parrot Flow

Current release: **[v0.2.0](https://github.com/Ankitrai97/parrot-flow/releases/tag/v0.2.0)**. See [CHANGELOG.md](CHANGELOG.md) for the reliability and dictation fixes in this version.

Parrot Flow is a local-first Windows dictation app. Press `Ctrl+Windows` (either Windows-logo key) to start and stop recording; the final transcript is typed into the app you were using. Speech recognition runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), so your audio is not sent to a cloud transcription service.

![License](https://img.shields.io/badge/license-MIT-8b5cf6)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0ea5e9)

## Features

- Local GPU-accelerated transcription with NVIDIA CUDA, plus CPU fallback.
- Global `Ctrl+Windows` hotkey and a draggable floating Parrot Flow control.
- Start, stop, and cancel controls that preserve the target app for text insertion.
- Compact HTML/CSS floating control with an animated recording waveform and clear green/red status light.
- Optional Windows sign-in startup.
- No clipboard replacement and no cloud audio upload.

## Download and install

When a packaged release is available, download `ParrotFlow.zip` from the repository's **Releases** page, extract it, and run `ParrotFlow.exe`. Windows may show a SmartScreen prompt for an unsigned open-source build; inspect the repository and choose **More info → Run anyway** only if you trust the release.

Startup prepares the selected Whisper model and caches it locally. The amber control shows preparation and transcription; errors show a readable message. Click the status light or press `Ctrl+Windows` to start/stop, **■** to stop and transcribe, **−** to hide the control, or **×** to cancel. Opening Parrot Flow again brings the existing control back.

## GPU support

Parrot Flow defaults to CUDA with FP16 on supported NVIDIA GPUs. The `small` Whisper model is a good balance for an RTX 3050 with 6 GB of VRAM. If CUDA is unavailable, the app temporarily falls back to CPU so dictation remains usable.

The packaged build includes the CUDA runtime libraries, but users still need a current NVIDIA graphics driver. On machines without a supported NVIDIA GPU, use CPU mode:

```toml
# %APPDATA%\ParrotFlow\config.toml
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
& .\.venv\Scripts\parrot-flow.exe
```

To start it automatically when you sign in:

```powershell
& .\.venv\Scripts\parrot-flow.exe --install-startup
```

To add Parrot Flow to Windows search and the Start Menu:

```powershell
& .\.venv\Scripts\parrot-flow.exe --install-app
```

Use `--remove-startup` or `--remove-app` to remove those entries later.

## Build a Windows release

From an activated development setup:

```powershell
.\packaging\build_windows.ps1
```

The application is created at `dist\ParrotFlow\ParrotFlow.exe`. Zip the entire `dist\ParrotFlow` folder—do not distribute the `.exe` by itself.

## Configuration

Parrot Flow stores its configuration at `%APPDATA%\ParrotFlow\config.toml`. Existing settings from `%APPDATA%\LocalDictate\config.toml` are copied forward automatically. Useful options include:

```toml
hotkey = "ctrl+windows"
microphone_name = "Microphone Array (Realtek(R) Audio)"
model = "small"
device = "cuda"
compute_type = "float16"
```

## Troubleshooting

Logs are at `%LOCALAPPDATA%\ParrotFlow\logs\parrot-flow.log`. A saved `microphone_name` takes priority over a numeric microphone ID and is resolved on every recording. If the microphone is missing, the control reports it instead of silently switching to a virtual input. Native microphone sample rates are converted to Whisper's 16 kHz locally.

The model health check exercises inference, including CUDA DLL loading. Diagnostic output can be saved even from the windowed EXE:

```powershell
.\dist\ParrotFlow\ParrotFlow.exe --check-model --diagnostic-output model-check.json
.\dist\ParrotFlow\ParrotFlow.exe --test-mic --diagnostic-output mic-check.txt
.\dist\ParrotFlow\ParrotFlow.exe --transcribe-file test.wav --diagnostic-output transcript.json
```

Live preview is disabled by default because the compact control does not show transcript text. This avoids repeated inference competing with final transcription. Silence does not stop dictation unless `auto_stop_on_silence = true` is explicitly enabled.

Final dictation uses five-beam decoding and keeps quiet words instead of applying a second voice filter. Text insertion waits for shortcut modifiers to be released and sends paced Unicode keystrokes so controlled editors can keep the entire result. Keep the target text field focused until the amber processing control returns to its idle red light.

## Privacy

Parrot Flow records only while you activate it and processes audio locally. Audio is held in memory for transcription and is not written to disk by the app. The first use of each Whisper model downloads its model files from Hugging Face.

## Contributing

Contributions and bug reports are welcome. Please run the test suite before opening a pull request:

```powershell
& .\.venv\Scripts\python.exe -m pytest
```

## License

Parrot Flow is released under the [MIT License](LICENSE).
