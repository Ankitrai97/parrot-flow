from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from dataclasses import replace

import numpy as np

from .config import Settings


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings, self.logger, self._model = settings, logger, None
        # Keep add_dll_directory handles alive. Releasing a handle removes the
        # directory from Windows' DLL search path.
        self._dll_directory_handles: list[object] = []
        self._using_cpu_fallback = False

    def _get_model(self):
        if self._model is not None:
            return self._model
        self._configure_cuda_runtime()
        from faster_whisper import WhisperModel
        try:
            if self._using_cpu_fallback:
                self._model = WhisperModel(self.settings.model, device="cpu", compute_type="int8")
            else:
                self._model = WhisperModel(self.settings.model, device=self.settings.device,
                                          compute_type=self.settings.compute_type)
        except Exception:
            if self.settings.device != "cuda" or self._using_cpu_fallback:
                raise
            self.logger.exception("CUDA model initialization failed; falling back to CPU int8 for this session")
            self._activate_cpu_fallback()
            self._model = WhisperModel(self.settings.model, device="cpu", compute_type="int8")
        return self._model

    def warm_up(self) -> None:
        """Load the model before the first dictation so it is ready to respond."""
        self._get_model()
        if self._using_cpu_fallback:
            self.logger.warning("Parrot Flow is using CPU fallback for this session")
        else:
            self.logger.info("Parrot Flow GPU is ready: CUDA / %s", self.settings.compute_type)

    def _configure_cuda_runtime(self) -> None:
        """Expose pip-provided CUDA/cuDNN DLLs on Windows before CTranslate2 loads."""
        if self.settings.device != "cuda" or not hasattr(os, "add_dll_directory"):
            return
        nvidia_dir = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
        for folder in (
            nvidia_dir / "cuda_runtime" / "bin",
            nvidia_dir / "cublas" / "bin",
            nvidia_dir / "cudnn" / "bin",
        ):
            if folder.is_dir():
                self._dll_directory_handles.append(os.add_dll_directory(str(folder)))

    def transcribe(self, audio: np.ndarray) -> str:
        return self._transcribe(audio, log_result=True)

    def transcribe_preview(self, audio: np.ndarray) -> str:
        """Fast, non-persistent partial result for the recording HUD."""
        return self._transcribe(audio, log_result=False)

    def _transcribe(self, audio: np.ndarray, log_result: bool) -> str:
        if audio.size == 0:
            return ""
        try:
            segments, info = self._get_model().transcribe(
                audio,
                language=self.settings.language,
                vad_filter=True,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
            )
        except RuntimeError:
            if self.settings.device != "cuda" or self._using_cpu_fallback:
                raise
            self.logger.exception("CUDA inference failed; retrying this dictation on CPU int8 for this session")
            self._activate_cpu_fallback()
            return self._transcribe(audio, log_result)
        text = "".join(segment.text for segment in segments).strip()
        if log_result:
            self.logger.info("Transcribed %0.1fs (%s): %s", audio.size / self.settings.sample_rate,
                             info.language, text[:100])
        return text

    def _activate_cpu_fallback(self) -> None:
        self._using_cpu_fallback = True
        self._model = None
        self.settings = replace(self.settings, device="cpu", compute_type="int8")
        # Do not persist a transient CUDA failure. Otherwise one failed start
        # silently turns every later dictation into a much slower CPU job.
        self.logger.warning("CPU fallback is temporary; CUDA will be retried next time the app starts")
