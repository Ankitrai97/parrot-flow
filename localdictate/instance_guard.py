from __future__ import annotations

import ctypes


class SingleInstanceGuard:
    """Keep only one LocalDictate service active per Windows user session."""

    _MUTEX_NAME = r"Local\LocalDictate-Service"
    _ERROR_ALREADY_EXISTS = 183

    def __init__(self) -> None:
        self._handle: int | None = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        self._kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        self._kernel32.CloseHandle.restype = ctypes.c_bool

    def acquire(self) -> bool:
        handle = self._kernel32.CreateMutexW(None, False, self._MUTEX_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == self._ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def close(self) -> None:
        if self._handle is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None
