"""Opt-in native insertion test in a disposable, self-owned Tk text field."""
import ctypes
import json
import threading
import tkinter as tk

from localdictate.clipboard import ClipboardText
from localdictate.injection import WindowsTextInjector

TEXT = "Whole result, not streamed.\n" * 40 + "Final line: café, हिंदी, 🙂."
root = tk.Tk()
root.title("Parrot Flow disposable paste check")
field = tk.Text(root)
field.pack()
result = {}
injector = WindowsTextInjector()
clipboard = ClipboardText()


def work(target):
    try:
        with clipboard._open(None):
            before = dict(clipboard._snapshot())
        injector._dictation_target = target
        injector._dictation_pid = injector._own_process_id
        injector.inject(TEXT)
        with clipboard._open(None):
            after = dict(clipboard._snapshot())
        result["clipboard_preserved"] = before == after
        root.after(200, finish)
    except Exception as error:
        result["error"] = str(error)
        root.after(0, finish)


def finish():
    actual = field.get("1.0", "end-1c").replace("\r\n", "\n")
    result.update(exact_match=actual == TEXT, expected=len(TEXT), received=len(actual))
    injector.close()
    root.destroy()


def start():
    root.deiconify()
    root.lift()
    field.focus_force()
    root.update()
    get_ancestor = ctypes.windll.user32.GetAncestor
    get_ancestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    get_ancestor.restype = ctypes.c_void_p
    target = get_ancestor(root.winfo_id(), 2)
    threading.Thread(target=work, args=(target,), daemon=True).start()


root.after(500, start)
root.after(15000, lambda: (result.update(error="test timed out"), finish()))
root.mainloop()
print(json.dumps(result))
if not result.get("exact_match") or not result.get("clipboard_preserved"):
    raise SystemExit(1)
