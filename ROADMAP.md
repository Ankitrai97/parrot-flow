# Next release

Recorded from Ankit's November 2026 requests. These are planned, not shipped promises.

## Implemented for 0.3.1

- Personal dictionary in Settings: `heard phrase => preferred spelling`, one per line,
  longest whole phrase first, case-insensitive, no cascading replacements; applied after cleanup.
- Microphone meter driven by actual RMS samples, with stale-stream/quiet-signal tooltip feedback.
  A quiet signal is not proof that a microphone is muted; no automatic stop is introduced.
- Memory-only last-result review, editing, prepare-for-insertion and clear actions in Settings.
  Recovery never inserts until the user selects a destination and explicitly invokes Insert/hotkey.
  No on-disk history or crash recovery. Clear removes both pending and last-result copies.
- Native compact HUD, hover settings, tapered meter, soft cues and 7-second no-voice dismissal.
- Redesigned settings sections and no em dashes in settings.
- 86 automated tests pass; native render and settings layout smoke checks pass. Retain cross-app validation below.

## Release gates

- Verify complete insertion in Chrome/ChatGPT, WhatsApp, VS Code, Notion and native editors,
  including long text, Hindi, emoji, multiline input, clipboard formats and focus changes.
- Improve clipboard compatibility without losing the user's clipboard or transcript.
- Complete packaged-app end-to-end testing before promoting the beta to stable.
- Investigate Claude Code cleanup latency/timeouts; test Ollama end to end.

## Features

- Personal dictionary for names, brands, technical terms and preferred spellings.
- Live microphone level meter and clear disconnected/muted microphone feedback.
- Last-transcript preview and explicit recovery/retry; optional local history with clear
  retention/deletion controls. Current pending-result recovery is memory-only, not crash recovery.
- Refine Fast / AI cleanup switch and expose provider readiness and latency. The basic toggle
  already ships in 0.3.0 beta; don't rebuild it as a new feature.
- Signed installer and a safe update/rollback flow; current distribution is a portable ZIP.

No automatic recording, silent cloud opt-in, or unrestricted agent access to project files.
