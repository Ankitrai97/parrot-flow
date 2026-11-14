# Parrot Flow v0.3.0-beta.2

Clipboard compatibility hotfix for Windows 10/11 x64. This is a **prerelease**;
v0.2.2 remains the stable release.

- Fixes beta.1 refusing dictation when the clipboard held a screenshot/image with
  PNG, DIBV5 and Windows OLE formats. The app now preserves transferable data
  and does not replay stale OLE bookkeeping pointers.
- Tested automatic insertion of a synthetic 1,147-character multiline transcript
  containing Hindi and emoji into a real native text field. Text matched exactly,
  and the image clipboard data remained intact. 64 automated tests passed.
- Other beta.1 features (fast transcription, protected controls, optional AI
  cleanup, in-memory pending transcript) remain unchanged.

Download the Windows ZIP and **extract the entire ParrotFlow folder** before
running `ParrotFlow.exe`. This is a portable unsigned build, not an installer.
Do not run two versions at once. CUDA libraries are bundled; the graphics driver
and local Whisper model may still be needed separately. Codex/Claude cleanup
is opt-in and sends transcript text to the chosen provider; speech audio stays local.

If clipboard contents still cannot be safely preserved, the transcript remains
pending instead of risking data loss. This beta has not been validated in every
editor. See [ROADMAP.md](https://github.com/Ankitrai97/parrot-flow/blob/v0.3.0-beta.2/ROADMAP.md)
for remaining compatibility work and the next features.
