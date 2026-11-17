# Parrot Flow 0.3.1

Windows 10/11 x64 local-first dictation with a smaller native interface.

## Changes

- Tiny two-dot idle pill at the bottom of the primary screen, expanding rightward for settings on hover.
- Smooth per-pixel-alpha corners, smaller recording controls and a center-peaked live microphone waveform.
- Compact no-voice notice that returns to idle after 7 seconds. Pending transcripts do not time out.
- Redesigned Dictation, Dictionary and Recovery settings sections, without em dashes.
- Personal dictionary and editable memory-only last-transcript recovery.
- Quiet ready and successful-insertion sounds.
- Includes the clipboard compatibility fixes from 0.3.0-beta.2.

## Download and run

Download `ParrotFlow-v0.3.1-windows-x64.zip`, extract the entire folder and run
`ParrotFlow.exe`. Do not move the EXE out of its bundled folder. Close your previous
Parrot Flow instance before starting this version. The default shortcut is Ctrl+Windows.
The bundled GPU libraries make the download large. The speech model may download separately
on first use; transcription stays local. Optional AI cleanup can send transcript text
to the selected provider.

This is an unsigned portable application, not a signed installer. Existing source-based
startup shortcuts are not automatically migrated to this extracted folder.

## Validation and limitations

- 86 automated tests pass.
- Native rendering checks verify transparent corners, antialiased edges and hover geometry.
- Settings layout checks pass at both 780px and 580px widths.
- Recovery is memory-only and is cleared on app exit. It is not crash recovery.
- Broad manual testing across every target app and mixed-DPI/multi-monitor configuration
  is incomplete. The control is anchored to the primary screen.
- Review important AI-cleaned text. No claim of bug-free operation or universal editor compatibility.

See the accompanying SHA256 file to verify the downloaded ZIP.
