from __future__ import annotations

import ctypes


class SingleInstanceGuard:
    """Keep only one Parrot Flow service active per Windows user session."""

    # Keep the original mutex name so a running pre-rename process cannot be
    # duplicated by a newer Parrot Flow launch.
    _MUTEX_NAME = r"Local\LocalDictate-Service"
    _SHOW_EVENT_NAME = r"Local\ParrotFlow-Show"
    _ERROR_ALREADY_EXISTS = 183

    def __init__(self) -> None:
        self._handle: int | None = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        self._kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        self._kernel32.CloseHandle.restype = ctypes.c_bool
        self._kernel32.CreateEventW.argtypes = (ctypes.c_void_p, ctypes.c_bool,
                                               ctypes.c_bool, ctypes.c_wchar_p)
        self._kernel32.CreateEventW.restype = ctypes.c_void_p
        self._kernel32.SetEvent.argtypes = (ctypes.c_void_p,)
        self._kernel32.SetEvent.restype = ctypes.c_bool
        self._kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        self._kernel32.WaitForSingleObject.restype = ctypes.c_ulong
        self._show_event: int | None = None

    def acquire(self) -> bool:
        handle = self._kernel32.CreateMutexW(None, False, self._MUTEX_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == self._ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            event = self._kernel32.CreateEventW(None, False, False, self._SHOW_EVENT_NAME)
            if event:
                self._kernel32.SetEvent(event)
                self._kernel32.CloseHandle(event)
            return False
        self._handle = handle
        self._show_event = self._kernel32.CreateEventW(None, False, False, self._SHOW_EVENT_NAME)
        return True

    def wait_for_show(self, timeout_ms: int = 250) -> bool:
        return bool(self._show_event and
                    self._kernel32.WaitForSingleObject(self._show_event, timeout_ms) == 0)

    def close(self) -> None:
        if self._handle is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._show_event is not None:
            self._kernel32.CloseHandle(self._show_event)
            self._show_event = None
