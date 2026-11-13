"""Temporary, text-only clipboard transaction; never destroy an unknown format."""
from __future__ import annotations

import ctypes
import time
from contextlib import contextmanager
from ctypes import wintypes


class ClipboardUnavailable(RuntimeError):
    pass


class ClipboardText:
    def __init__(self):
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("OpenClipboard", [wintypes.HWND], wintypes.BOOL),
            ("CloseClipboard", [], wintypes.BOOL),
            ("EmptyClipboard", [], wintypes.BOOL),
            ("EnumClipboardFormats", [wintypes.UINT], wintypes.UINT),
            ("GetClipboardData", [wintypes.UINT], wintypes.HANDLE),
            ("SetClipboardData", [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE),
            ("RegisterClipboardFormatW", [wintypes.LPCWSTR], wintypes.UINT),
            ("GetClipboardSequenceNumber", [], wintypes.DWORD),
            ("CreateWindowExW", [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HWND),
            ("DestroyWindow", [wintypes.HWND], wintypes.BOOL),
        ):
            fn = getattr(self.u, name)
            fn.argtypes, fn.restype = args, result
        for name, args, result in (
            ("GlobalAlloc", [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL),
            ("GlobalLock", [wintypes.HGLOBAL], ctypes.c_void_p),
            ("GlobalUnlock", [wintypes.HGLOBAL], wintypes.BOOL),
            ("GlobalSize", [wintypes.HGLOBAL], ctypes.c_size_t),
            ("GlobalFree", [wintypes.HGLOBAL], wintypes.HGLOBAL),
        ):
            fn = getattr(self.k, name)
            fn.argtypes, fn.restype = args, result
        self.private_formats = [self.u.RegisterClipboardFormatW(name) for name in
                                ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")]
        self.safe_formats = {1, 7, 13, 16, *self.private_formats,
                             self.u.RegisterClipboardFormatW("HTML Format"),
                             self.u.RegisterClipboardFormatW("Rich Text Format")}

    @contextmanager
    def _open(self, owner):
        deadline = time.monotonic() + 0.3
        while not self.u.OpenClipboard(owner):
            if time.monotonic() > deadline:
                raise ClipboardUnavailable("Clipboard is busy")
            time.sleep(0.01)
        try:
            yield
        finally:
            self.u.CloseClipboard()

    def _snapshot(self):
        saved = []
        fmt = 0
        while True:
            ctypes.set_last_error(0)
            fmt = self.u.EnumClipboardFormats(fmt)
            if not fmt:
                if ctypes.get_last_error():
                    raise ClipboardUnavailable("Cannot enumerate clipboard")
                break
            if fmt not in self.safe_formats:
                raise ClipboardUnavailable("Clipboard contains non-text or private data")
            handle = self.u.GetClipboardData(fmt)
            size = self.k.GlobalSize(handle) if handle else 0
            if not size or size > 16 * 1024 * 1024:
                raise ClipboardUnavailable("Clipboard cannot be safely preserved")
            pointer = self.k.GlobalLock(handle)
            if not pointer:
                raise ClipboardUnavailable("Cannot read clipboard data")
            try:
                saved.append((fmt, ctypes.string_at(pointer, size)))
            finally:
                self.k.GlobalUnlock(handle)
        return saved

    def _set(self, fmt, data):
        handle = self.k.GlobalAlloc(0x0002, len(data))
        if not handle:
            raise ClipboardUnavailable("Clipboard allocation failed")
        try:
            pointer = self.k.GlobalLock(handle)
            if not pointer:
                raise ClipboardUnavailable("Cannot lock clipboard allocation")
            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                self.k.GlobalUnlock(handle)
            if not self.u.SetClipboardData(fmt, handle):
                raise ClipboardUnavailable("Cannot publish clipboard data")
            handle = None  # Windows now owns the allocation.
        finally:
            if handle:
                self.k.GlobalFree(handle)

    def _replace(self, items):
        if not self.u.EmptyClipboard():
            raise ClipboardUnavailable("Cannot clear clipboard")
        for fmt, data in items:
            self._set(fmt, data)

    @contextmanager
    def temporary(self, text):
        # A real owner HWND is required by EmptyClipboard/SetClipboardData.
        owner = self.u.CreateWindowExW(0, "STATIC", "ParrotFlowClipboard", 0,
                                       0, 0, 0, 0, None, None, None, None)
        if not owner:
            raise ClipboardUnavailable("Cannot create clipboard owner")
        saved, sequence = None, None
        try:
            with self._open(owner):
                saved = self._snapshot()
                try:
                    self._replace([(fmt, b"\0\0\0\0") for fmt in self.private_formats]
                                  + [(13, (text.replace("\r\n", "\n").replace("\n", "\r\n")
                                           + "\0").encode("utf-16-le"))])
                except Exception:
                    self._replace(saved)
                    raise
                sequence = self.u.GetClipboardSequenceNumber()
            yield
        finally:
            try:
                if sequence is not None:
                    with self._open(owner):
                        # Never undo a copy the user made while we were pasting.
                        if self.u.GetClipboardSequenceNumber() == sequence:
                            self._replace(saved)
            finally:
                self.u.DestroyWindow(owner)
