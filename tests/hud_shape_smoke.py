"""Opt-in native HUD rendering check; no microphone, clipboard or dictation."""
import time
from pathlib import Path
from localdictate.hud import RecordingHud

failures = []


def check():
    try:
        from System import Action
        from System.Drawing import Bitmap
        output = Path('outputs').resolve()
        output.mkdir(exist_ok=True)
        for state in ('idle', 'recording', 'error'):
            hud._render_dump = str(output / ('hud-' + state + '.png'))
            hud.show_status(state, 'No voice detected. Check your microphone or mute switch.')
            time.sleep(1)
            def inspect():
                pill = hud._pill
                pill.level = .8
                pill.render()
                assert pill.form.Visible
                if state == 'idle':
                    left = pill.form.Left
                    pill.enter()
                    assert pill.expanded
                    assert pill.form.Width >= 70
                    assert pill.form.Left == left
                    pill.expanded = False
                    pill.render()
            hud._window.native.Invoke(Action(inspect))
            image = Bitmap(hud._render_dump)
            try:
                assert image.GetPixel(0, 0).A == 0
                assert image.GetPixel(image.Width//2, image.Height//2).A == 255
                assert any(0 < image.GetPixel(x,y).A < 255
                           for x in range(image.Width) for y in range(image.Height))
                print(state, image.Size, 'transparent corners and antialiased edges verified', flush=True)
            finally:
                image.Dispose()
    except Exception:
        import traceback
        traceback.print_exc()
        failures.append(True)
    finally:
        hud.close()


hud = RecordingHud(lambda: None, on_ready=check, title='Parrot Flow — render verification')
hud.run()
raise SystemExit(bool(failures))
