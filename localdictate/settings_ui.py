"""Small native settings window sharing the existing webview event loop."""
from dataclasses import replace

import webview

from .config import save_settings


def updated_settings(current, values):
    if not isinstance(values, dict):
        raise TypeError("Invalid settings")
    if type(values.get("enhance_with_llm")) is not bool:
        raise ValueError("Choose Fast or AI cleanup mode")
    provider = values.get("enhancement_provider")
    insertion = values.get("insertion_mode")
    beam = values.get("beam_size")
    timeout = values.get("enhancement_timeout_seconds")
    model = values.get("enhancement_model", "")
    if provider not in {"codex", "claude", "ollama"}:
        raise ValueError("Choose a supported AI provider")
    if insertion not in {"paste", "unicode", "paced"}:
        raise ValueError("Choose an insertion method")
    if type(beam) is not int or beam not in {1, 5}:
        raise ValueError("Choose Fast or Balanced recognition")
    if type(timeout) is not int or not 5 <= timeout <= 60:
        raise ValueError("AI timeout must be between 5 and 60 seconds")
    if not isinstance(model, str) or len(model) > 120 or any(ord(c) < 32 for c in model):
        raise ValueError("Invalid model name")
    return replace(current, enhance_with_llm=values["enhance_with_llm"],
                   enhancement_provider=provider, enhancement_model=model.strip(),
                   enhancement_timeout_seconds=timeout, beam_size=beam,
                   insertion_mode=insertion, injection_delay_seconds=0.01 if insertion == "paced" else 0)


class SettingsApi:
    def __init__(self, controller, on_quit=None):
        self.controller = controller
        self.on_quit = on_quit

    def read(self):
        settings = self.controller.settings
        return {name: getattr(settings, name) for name in (
            "enhance_with_llm", "enhancement_provider", "enhancement_model",
            "enhancement_timeout_seconds", "insertion_mode", "beam_size", "hotkey")}

    def save(self, values):
        try:
            settings = updated_settings(self.controller.settings, values)
            self.controller.configure(settings, save_settings)
            return {"ok": True, "message": "Saved. Applies to your next dictation."}
        except (TypeError, ValueError, OSError) as error:
            return {"ok": False, "message": str(error)}

    def quit(self):
        if self.controller.busy or self.controller.recording or self.controller.pending_text:
            return "Finish or discard the current dictation before quitting."
        if self.on_quit:
            self.on_quit()
        return "Closing Parrot Flow…"


HTML = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Parrot Flow settings</title><style>
body{font:14px 'Segoe UI',sans-serif;background:#101827;color:#e9f0ff;margin:28px}
h1{font-size:24px;margin-bottom:4px}p{color:#aabbd3;line-height:1.55}
label{display:block;margin:18px 0 7px}select,input,button{font:inherit;border-radius:7px;
border:1px solid #45556d;padding:10px;background:#1d2a3e;color:#fff;box-sizing:border-box}
select,input{width:100%}button{cursor:pointer;background:#176749;margin-top:24px}
small{display:block;color:#aabbd3;margin:7px 0;line-height:1.5}
#feedback{min-height:30px;color:#9df2b3}#privacy{padding:12px;background:#293048;border-radius:8px}
</style><h1>Parrot Flow</h1><p>Speak naturally. Insert once.</p>
<small id="shortcut"></small>
<label for="mode">Writing mode</label><select id="mode">
<option value="fast">Fast — direct local transcript</option>
<option value="ai">AI cleanup — punctuation, repetitions, wording</option></select>
<div id="ai"><label for="provider">Cleanup provider</label><select id="provider">
<option value="codex">Codex CLI (signed-in account)</option>
<option value="claude">Claude Code CLI (signed-in account)</option>
<option value="ollama">Ollama (local server)</option></select>
<label for="model">AI model (blank uses CLI default)</label><input id="model" maxlength="120">
<small>For Ollama, enter an installed local model name. CLI sign-in and plan limits apply.</small>
<label for="timeout">Cleanup timeout in seconds</label><input id="timeout" type="number" min="5" max="60">
<p id="privacy">Codex/Claude sends transcript text to its provider. Audio stays local.
Ollama connects only to localhost. Cleanup may change meaning: review important text.
If cleanup fails or times out, the original transcript is used.</p></div>
<label for="quality">Speech recognition</label><select id="quality">
<option value="1">Fast — one decoding beam</option><option value="5">Balanced — five beams (slower)</option></select>
<label for="insertion">Text insertion</label><select id="insertion">
<option value="paste">Instant paste — entire result together</option>
<option value="paced">Compatibility — slower keyboard typing</option></select>
<small>Instant paste temporarily uses the clipboard and restores supported text formats.
If the clipboard is busy or has unsupported formats, the result is kept in memory: copy some
plain text, refocus your field, then press Insert. Compatibility typing is slower and editor-dependent;
newlines may act as Enter in chat apps. Paste does not press Enter.</small>
<button id="save">Save settings</button> <button id="quit">Quit Parrot Flow</button>
<p id="feedback" role="status"></p>
<script>
const el=id=>document.getElementById(id);
function refresh(){el('ai').hidden=el('mode').value==='fast';}
el('mode').onchange=refresh;
el('quit').onclick=async()=>{el('feedback').textContent=await window.pywebview.api.quit();};
window.addEventListener('pywebviewready', async()=>{
 const s=await window.pywebview.api.read();
 el('mode').value=s.enhance_with_llm?'ai':'fast';el('provider').value=s.enhancement_provider;
 el('model').value=s.enhancement_model;el('timeout').value=s.enhancement_timeout_seconds;
 el('quality').value=s.beam_size;el('insertion').value=s.insertion_mode==='unicode'?'paced':s.insertion_mode;
 el('shortcut').textContent='Shortcut: '+s.hotkey+' · press once to start, again to finish';refresh();
});
el('save').onclick=async()=>{
 el('save').disabled=true;
 try {const result=await window.pywebview.api.save({enhance_with_llm:el('mode').value==='ai',
 enhancement_provider:el('provider').value,enhancement_model:el('model').value,
 enhancement_timeout_seconds:Number(el('timeout').value),beam_size:Number(el('quality').value),
 insertion_mode:el('insertion').value});el('feedback').textContent=result.message;}
 catch(e){el('feedback').textContent='Unable to save settings. Please try again.';}
 finally{el('save').disabled=false;}
};</script></html>"""


class SettingsWindow:
    def __init__(self, controller, on_quit=None):
        self.window = webview.create_window("Parrot Flow — Settings", html=HTML,
                                           js_api=SettingsApi(controller, on_quit), width=560, height=790,
                                           hidden=True, min_size=(480, 480), background_color="#101827")
        self._closing = False
        self.window.events.closing += self._on_close

    def _on_close(self):
        if not self._closing:
            self.window.hide()
            return False

    def show(self):
        self.window.show()

    def close(self):
        if self._closing:
            return
        self._closing = True
        self.window.destroy()
