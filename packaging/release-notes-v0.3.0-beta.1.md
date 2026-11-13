# Parrot Flow v0.3.0-beta.1

This is a Windows x64 **prerelease**. v0.2.2 remains the stable release.

## Changes

- Separate drag handle and recording buttons; processing locks controls and ignores extra hotkeys.
- Whole-result automatic paste instead of deliberate character-by-character typing.
- Fast local recognition and optional AI cleanup, configurable through the settings gear.
- Codex CLI, Claude Code CLI and local Ollama adapters; original transcript used on cleanup failure.
- In-memory pending transcript when focus changes or insertion cannot proceed.
- Startup sequencing fix for the Windows UI/speech runtime race; transcript content removed from routine logs.

## Download

Download `ParrotFlow-v0.3.0-beta.1-windows-x64.zip`, extract the **entire folder**, and run
`ParrotFlow.exe`. Do not run two versions simultaneously. This is a portable unsigned build,
not a signed installer. The bundled CUDA libraries make the download large. Models are downloaded
separately on first use; NVIDIA drivers and Microsoft Edge WebView2 Runtime are prerequisites.

Existing config and downloaded models are reused. Fast mode is the default; AI cleanup is opt-in.
CLI cleanup requires an installed, signed-in CLI and is subject to that provider's limits.
Codex/Claude receives transcript text when enabled; speech recognition/audio stays local.

## Important beta limits

- Automatic keyboard fallback was **disabled** after a desktop completeness test failed. If the
  clipboard is busy or has unsupported formats, your clipboard is left unchanged and the transcript
  remains in memory. Copy any plain text, select the destination field and click Insert to retry.
- Explicit compatibility keyboard typing is slower and editor-dependent. Its newlines may trigger
  Enter actions in chat apps. Paste does not press Enter.
- Pending transcripts do not survive exit/crash. Focus checks are window-level, not every browser field.
- Paste has no reliable destination acknowledgment; review the result. Full packaged cross-app coverage
  remains pending, so this beta is not promoted to stable.
- Synthetic Codex cleanup passed. Claude exceeded the live-test timeout; Ollama is not live-verified.
- AI cleanup can change wording/meaning. Review important text.

## Validation and next release

63 automated Windows tests passed. The local CUDA benchmark transcribed a 7.5-second sample in
approximately 0.61 seconds with the fast setting (hardware/workload dependent, not a guarantee).

See [ROADMAP.md](https://github.com/Ankitrai97/parrot-flow/blob/v0.3.0-beta.1/ROADMAP.md) for the
personal dictionary, microphone meter, fuller transcript recovery, compatibility testing and installer work.
