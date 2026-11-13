# Next release

Recorded from Ankit's November 2026 requests. These are planned, not shipped promises.

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
