"""Small native settings window sharing the existing webview event loop."""
from dataclasses import replace

import webview

from .config import save_settings
from .dictionary import parse_rules


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
    dictionary = values.get("dictionary_rules", current.dictionary_rules)
    parse_rules(dictionary)
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
                   insertion_mode=insertion, injection_delay_seconds=0.01 if insertion == "paced" else 0,
                   dictionary_rules=dictionary)


class SettingsApi:
    def __init__(self, controller, on_quit=None):
        self.controller = controller
        self.on_quit = on_quit

    def read(self):
        settings = self.controller.settings
        return {name: getattr(settings, name) for name in (
            "enhance_with_llm", "enhancement_provider", "enhancement_model",
            "enhancement_timeout_seconds", "insertion_mode", "beam_size", "hotkey", "dictionary_rules")}

    def recovery(self, action, text=""):
        try:
            if action == "prepare":
                self.controller.prepare_recovery(text)
                return {"ok": True, "message": "Ready. Select your destination, then press the hotkey or Insert."}
            if action == "clear":
                self.controller.clear_recovery()
            elif action != "read":
                raise ValueError("Unknown recovery action")
            return {"ok": True, "text": self.controller.recovery_text(), "message": "Memory-only; cleared when the app exits."}
        except ValueError as error:
            return {"ok": False, "message": str(error)}

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


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parrot Flow settings</title>
<style>
:root{color-scheme:light;--bg:#f7f8fa;--surface:#fff;--ink:#20262c;--muted:#647078;--line:#e5e9e8;--green:#147d59}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI Variable","Segoe UI",Arial,sans-serif;font-size:13px;line-height:1.55}
button,input,select,textarea{font-family:inherit;font-size:inherit}button{cursor:pointer}button:disabled{cursor:wait;opacity:.5}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #90d8ba;outline-offset:3px}
.app{display:grid;grid-template-columns:170px 1fr;min-height:100vh}
aside{padding:28px 16px;border-right:1px solid var(--line);background:#fff;position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
.brand{font-size:16px;font-weight:700;letter-spacing:-.4px;display:flex;gap:9px;align-items:center;padding:0 8px}
.mark{display:inline-grid;place-items:center;width:25px;height:25px;border-radius:9px;background:#def4e8;color:var(--green)}
.caption{font-size:10px;text-transform:uppercase;letter-spacing:1.6px;color:#83908b;margin:32px 10px 10px}
nav{display:grid;gap:5px}.nav{border:0;background:transparent;border-radius:9px;padding:11px 12px;text-align:left;color:var(--muted);font-weight:600}
.nav[aria-selected=true]{color:#136b4c;background:#eaf6ef}.nav:hover{background:#f1f5f3}
.aside-bottom{margin-top:auto;padding:18px 8px 0;color:var(--muted);font-size:11px}.status-dot{display:inline-block;background:#28ad76;width:6px;height:6px;border-radius:50%;margin-right:6px}
main{padding:32px 34px 90px;min-width:0;max-width:900px}
.eyebrow{font-size:10px;letter-spacing:1.7px;font-weight:700;color:var(--green);text-transform:uppercase}
h1{font-size:27px;letter-spacing:-.9px;line-height:1.2;margin:6px 0 10px;font-weight:650}h2{font-size:14px;margin:0;font-weight:650}
p{margin:6px 0 18px;color:var(--muted)}.subtitle{font-size:13px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;margin:18px 0;padding:20px}
.row{display:grid;grid-template-columns:1fr 185px;align-items:center;gap:18px;padding:15px 0;border-bottom:1px solid #eef1ef}.row:first-child{padding-top:0}.row:last-child{border:0;padding-bottom:0}
label{font-weight:600;display:block;margin-bottom:5px}.hint,small{display:block;color:var(--muted);font-size:11px;line-height:1.6}
select,input,textarea{color:var(--ink);border:1px solid #dbe2df;border-radius:8px;padding:10px 11px;background:#fafcfb;width:100%;min-width:0}
textarea{resize:vertical;line-height:1.7}textarea::placeholder,input::placeholder{color:#929b97}
#dictionary{font-family:Consolas,monospace;font-size:12px;min-height:165px}#recovery{min-height:190px;margin:16px 0}
.ai-fields{border-top:1px solid var(--line);padding-top:18px;margin-top:18px}.field{margin:14px 0}
.note{background:#f0f7f3;border-radius:9px;color:#4e6f60;padding:12px 14px;font-size:11px;margin:14px 0 0}
details{margin-top:15px;color:var(--muted);font-size:11px}summary{cursor:pointer;color:#4e6459;font-weight:600}
.shortcut{display:flex;align-items:center;gap:12px;color:var(--muted);font-size:11px;margin:18px 0}kbd{font-family:inherit;background:#fff;border:1px solid var(--line);border-bottom-width:2px;border-radius:7px;padding:5px 9px;color:#3d4a43;font-weight:600}
.actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.btn{border:1px solid #dae3dd;background:#fff;color:#34463b;border-radius:8px;padding:9px 14px;font-weight:600;transition:background .12s}
.btn:hover{background:#f0f5f2}.primary{background:var(--green);border-color:var(--green);color:white}.primary:hover{background:#106746}
.quiet{padding:6px 0;border:0;background:none;color:#7b8580;font-size:11px}.danger:hover{color:#a63d3d}
footer{position:fixed;bottom:0;left:170px;right:0;min-height:65px;padding:14px 34px;background:#ffffffed;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:14px}
#feedback,#recovery-status{font-size:12px;color:var(--green);margin:0;white-space:normal}#recovery-status{margin-top:14px}
.example{display:flex;gap:8px;align-items:center;padding:12px 14px;background:#f7f9f8;border-radius:9px;font-family:Consolas,monospace;font-size:12px;margin:15px 0}.arrow{color:#95a29b}
[hidden]{display:none!important}
@media(max-width:620px){.app{grid-template-columns:130px 1fr}aside{padding:22px 10px}.brand{font-size:13px;gap:6px}main{padding:26px 20px 95px}footer{left:130px;padding:12px 20px}.row{grid-template-columns:1fr;gap:9px}h1{font-size:24px}}
</style></head>
<body><div class="app">
<aside><div class="brand"><span class="mark" aria-hidden="true">P</span>Parrot Flow</div>
<div class="caption">Workspace</div>
<nav aria-label="Settings sections" role="tablist">
<button class="nav" id="tab-dictation" role="tab" aria-selected="true" aria-controls="dictation" data-panel="dictation">Dictation</button>
<button class="nav" id="tab-dictionary-panel" role="tab" aria-selected="false" aria-controls="dictionary-panel" data-panel="dictionary-panel">Dictionary</button>
<button class="nav" id="tab-recovery-panel" role="tab" aria-selected="false" aria-controls="recovery-panel" data-panel="recovery-panel">Recovery</button>
</nav><div class="aside-bottom"><div><span class="status-dot"></span>Local transcription</div>
<button class="quiet danger" id="quit">Quit Parrot Flow</button></div></aside>
<main>
<section id="dictation" role="tabpanel" aria-labelledby="tab-dictation">
<div class="eyebrow">Make it yours</div><h1>Your voice. Your flow.</h1><p class="subtitle">A few thoughtful defaults. Less time between speaking and writing.</p>
<div class="shortcut"><kbd id="shortcut">Loading shortcut</kbd><span>Press to start. Press again to finish.</span></div>
<div class="card">
<div class="row"><div><label for="mode">Writing mode</label><small>Keep your words or give them a light polish.</small></div>
<select id="mode"><option value="fast">Fast, local transcript</option><option value="ai">AI cleanup</option></select></div>
<div class="row"><div><label for="quality">Recognition quality</label><small>Choose speed or a more detailed decoding pass.</small></div>
<select id="quality"><option value="1">Fast</option><option value="5">Balanced</option></select></div>
<div class="row"><div><label for="insertion">Text insertion</label><small>Insert the complete result in one action.</small></div>
<select id="insertion"><option value="paste">Instant paste</option><option value="paced">Compatibility typing</option></select></div>
<div id="ai" class="ai-fields" hidden><h2>AI cleanup</h2>
<div class="field"><label for="provider">Provider</label><select id="provider"><option value="codex">Codex CLI</option><option value="claude">Claude Code CLI</option><option value="ollama">Ollama, local</option></select></div>
<div class="field"><label for="model">Model</label><input id="model" maxlength="120" placeholder="Default CLI model"><small>For Ollama, enter an installed model name. CLI sign-in and plan limits apply.</small></div>
<div class="field"><label for="timeout">Timeout in seconds</label><input id="timeout" type="number" min="5" max="60"></div>
<div id="privacy" class="note">Codex and Claude send transcript text to their provider. Audio stays local. Ollama connects to localhost only. If cleanup fails, your original transcript is used. Review important text because AI can change meaning.</div></div>
<details><summary>Clipboard and compatibility details</summary><p>Instant paste temporarily uses your clipboard and restores supported formats. If insertion fails, the result stays in memory for recovery. Compatibility typing is slower, and newlines can act as Enter in chat apps. Paste does not press Enter.</p></details>
</div><div class="note">No voice input? The control returns to idle after 7 seconds. Saved transcripts remain available until you insert or clear them.</div>
</section>
<section id="dictionary-panel" role="tabpanel" aria-labelledby="tab-dictionary-panel" hidden>
<div class="eyebrow">Your vocabulary</div><h1>Words that sound like you.</h1><p class="subtitle">Give names, brands and technical terms the spelling they deserve.</p>
<div class="card"><label for="dictionary">Personal dictionary</label><small>One heard phrase and its preferred spelling per line.</small>
<div class="example"><span>parrot low</span><span class="arrow">=&gt;</span><span>Parrot Flow</span></div>
<textarea id="dictionary" rows="7" maxlength="12000" placeholder="parrot low => Parrot Flow"></textarea>
<small>Whole phrases, case-insensitive. Applied after AI cleanup. Replacements do not cascade.</small></div></section>
<section id="recovery-panel" role="tabpanel" aria-labelledby="tab-recovery-panel" hidden>
<div class="eyebrow">Nothing lost in the moment</div><h1>Pick up your last words.</h1><p class="subtitle">Review or edit the latest transcript before trying insertion again.</p>
<div class="card"><div class="actions"><h2 style="flex:1">Last transcript</h2><button class="btn" id="load-result">Load last result</button></div>
<textarea id="recovery" rows="7" maxlength="100000" aria-label="Recovered transcript" placeholder="Load your last result to review it here."></textarea>
<div class="actions"><button class="btn primary" id="prepare-result">Prepare for insertion</button><button class="btn" id="clear-result">Clear result</button></div>
<p id="recovery-status" role="status"></p><div class="note">Memory only, not saved to disk. Closing the app clears recovery. Check your destination for existing text before retrying to avoid duplicates.</div></div></section>
</main><footer><span id="feedback" role="status">Loading settings…</span><button class="btn primary" id="save" disabled>Save changes</button></footer></div>
<script>
const el=id=>document.getElementById(id);
document.querySelectorAll('[data-panel]').forEach(button=>{
 button.onclick=()=>{
  document.querySelectorAll('[role=tabpanel]').forEach(panel=>panel.hidden=panel.id!==button.dataset.panel);
  document.querySelectorAll('[data-panel]').forEach(tab=>tab.setAttribute('aria-selected',String(tab===button)));
  el('save').hidden=button.dataset.panel==='recovery-panel';
 };
});
function refresh(){el('ai').hidden=el('mode').value==='fast';}
el('mode').onchange=refresh;
async function recover(action){
 try{const r=await window.pywebview.api.recovery(action,el('recovery').value);
 el('recovery-status').textContent=r.message;
 if(r.ok && 'text' in r)el('recovery').value=r.text;
 }catch(e){el('recovery-status').textContent='Recovery unavailable. Try again.';}
}
el('load-result').onclick=()=>recover('read');
el('prepare-result').onclick=()=>recover('prepare');
el('clear-result').onclick=()=>recover('clear');
el('quit').onclick=async()=>{el('feedback').textContent=await window.pywebview.api.quit();};
window.addEventListener('pywebviewready', async()=>{
 try {
 const s=await window.pywebview.api.read();
 el('mode').value=s.enhance_with_llm?'ai':'fast';el('provider').value=s.enhancement_provider;
 el('model').value=s.enhancement_model;el('timeout').value=s.enhancement_timeout_seconds;
 el('dictionary').value=s.dictionary_rules;
 el('quality').value=s.beam_size;el('insertion').value=s.insertion_mode==='unicode'?'paced':s.insertion_mode;
 el('shortcut').textContent=s.hotkey.replaceAll('+',' + ');refresh();
 el('save').disabled=false;el('feedback').textContent='Changes apply to your next dictation.';
 } catch(e) {el('feedback').textContent='Could not load settings. Close and reopen this window.';}
});
el('save').onclick=async()=>{
 el('save').disabled=true;
 try {const result=await window.pywebview.api.save({enhance_with_llm:el('mode').value==='ai',
 enhancement_provider:el('provider').value,enhancement_model:el('model').value,
 enhancement_timeout_seconds:Number(el('timeout').value),beam_size:Number(el('quality').value),
 insertion_mode:el('insertion').value,dictionary_rules:el('dictionary').value});el('feedback').textContent=result.message;}
 catch(e){el('feedback').textContent='Unable to save settings. Please try again.';}
 finally{el('save').disabled=false;}
};</script></body></html>"""


class SettingsWindow:
    def __init__(self, controller, on_quit=None):
        self.window = webview.create_window("Parrot Flow Settings", html=HTML,
                                           js_api=SettingsApi(controller, on_quit), width=780, height=720,
                                           hidden=True, min_size=(580, 480), background_color="#f7f8fa")
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
