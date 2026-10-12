# Changelog

## 0.2.1 - 2026-10-12

- Launch idle with the microphone off; background model preparation no longer displays a transcription-like state.
- Read current Windows key state instead of cached hook state, preventing a stale Ctrl press from turning Windows search into dictation.
- Ignore keys held during launch and queued launch events. Arm the shortcut after all its keys are released; require a fresh shortcut press.
- Require a trusted user click for the HUD recording action. The Stop button only stops an existing recording and cannot start another one.
- Log the recording input source to help distinguish button presses from shortcut activation.
- Added startup, held-key, stale-key, and HUD regression tests. All 32 Windows tests passed.

## 0.2.0 - 2026-10-11

Parrot Flow's second release improves launch reliability and complete dictation.

### Fixed

- Relaunching the app reveals the existing control instead of silently exiting. Model preparation, readiness, and errors are visible; failed preparation can be retried.
- Named microphone selection survives device-ID changes. Native microphone sample rates are resampled for Whisper; overflow retains recorded audio, and stream cleanup is reliable.
- Packaged CUDA runtime libraries are registered before inference. Startup verifies real inference, and CUDA failures retry the recording on CPU without saving a permanent fallback.
- Final transcription uses beam size 5 and avoids removing quiet words with a second voice-activity filter.
- Text insertion waits for shortcut modifiers to be released, paces Unicode characters, and preserves the original destination. Insertion failures report an error.
- Hotkey, recording, cancellation, and processing states remain synchronized. Microphone and inference errors recover to a usable state.
- Windowed launches write diagnostic logs safely without console streams. Background preview is disabled by default.

### Added

- Model health checks and local audio-file transcription, including diagnostic reports from the windowed executable.
- Stable microphone-name and text-insertion-delay settings.
- Parrot Flow Windows Start Menu and installed-app registration, with migration from legacy LocalDictate configuration and startup entries.
- Regression coverage for audio resampling, CUDA retries, duplicate launches, cancellation, and complete Unicode text insertion.

### Validation

- 25 tests passed on Windows.
- Packaged CUDA inference and a complete-sentence live dictation check passed.

## 0.1.0 - 2026-08-15

- Initial public release with local Windows dictation, NVIDIA CUDA/FP16 acceleration, CPU fallback, a global shortcut, and a floating control.
