"""Opt-in settings layout smoke test. Does not modify user settings."""
from dataclasses import asdict
import time
import webview
from localdictate.config import Settings
from localdictate.settings_ui import HTML


class PreviewApi:
    def read(self):
        return asdict(Settings())


failures = []


def check():
    try:
        window.events.loaded.wait()
        for _ in range(50):
            if window.evaluate_js("!document.getElementById('save').disabled"):
                break
            time.sleep(.1)
        assert window.evaluate_js("!document.getElementById('save').disabled")
        for width in (780, 580):
            window.resize(width, 720)
            for section in ('dictation', 'dictionary-panel', 'recovery-panel'):
                window.evaluate_js(f"document.getElementById('tab-{section}').click()")
                result = window.evaluate_js("""({
                  panels: [...document.querySelectorAll('[role=tabpanel]')].filter(p=>!p.hidden).length,
                  overflow: document.documentElement.scrollWidth > window.innerWidth,
                  font: getComputedStyle(document.body).fontFamily,
                  recovery: !document.getElementById('recovery-panel').hidden,
                  saveHidden: document.getElementById('save').hidden
                })""")
                assert result['panels'] == 1 and not result['overflow'], result
                assert result['saveHidden'] == result['recovery'], result
                assert 'Segoe UI' in result['font'], result
                print(width, section, 'passed', flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        failures.append(True)
    finally:
        window.destroy()


window = webview.create_window('Parrot Flow settings preview', html=HTML, js_api=PreviewApi(),
                               width=780, height=720)
webview.start(check, private_mode=True)
raise SystemExit(bool(failures))
