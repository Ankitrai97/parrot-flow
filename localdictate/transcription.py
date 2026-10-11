from __future__ import annotations

import gc
import logging
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from .config import Settings


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings, self.logger, self._model = settings, logger, None
        # Keep add_dll_directory handles alive. Releasing a handle removes the
        # directory from Windows' DLL search path.
        self._dll_directory_handles: list[object] = []
        self._using_cpu_fallback = False
        self._runtime_configured = False

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
        # Loading weights doesn't exercise CUDA DLLs. Force encoding and consume
        # the lazy segment iterator before claiming the device is ready.
        self._transcribe(np.zeros(self.settings.sample_rate, dtype=np.float32),
                         log_result=False, vad_filter=False)
        if self._using_cpu_fallback:
            self.logger.warning("Parrot Flow is using CPU fallback for this session")
        else:
            self.logger.info("Parrot Flow inference ready: %s / %s", self.settings.device,
                             self.settings.compute_type)

    def _configure_cuda_runtime(self) -> None:
        """Expose pip-provided CUDA/cuDNN DLLs on Windows before CTranslate2 loads."""
        if (self._runtime_configured or self.settings.device != "cuda"
                or not hasattr(os, "add_dll_directory")):
            return
        roots = [Path(sys.prefix) / "Lib" / "site-packages"]
        if getattr(sys, "frozen", False):
            roots.insert(0, Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        folders = [root / "nvidia" / library / "bin" for root in roots
                   for library in ("cuda_runtime", "cublas", "cudnn", "cuda_nvrtc")]
        existing = list(dict.fromkeys(str(folder) for folder in folders if folder.is_dir()))
        for folder in existing:
            self._dll_directory_handles.append(os.add_dll_directory(folder))
        # CTranslate2 uses LoadLibrary for CUDA at inference time, which also
        # needs PATH. Change only this process, not Windows' global environment.
        if existing:
            os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
        self._runtime_configured = True
        self.logger.info("CUDA runtime search directories: %s", existing)

    def transcribe(self, audio: np.ndarray) -> str:
        # Toggle dictation already trims the outer silence. Avoid removing quiet
        # words a second time with VAD, especially at the end of a sentence.
        return self._transcribe(audio, log_result=True, vad_filter=False)

    def transcribe_preview(self, audio: np.ndarray) -> str:
        """Fast, non-persistent partial result for the recording HUD."""
        return self._transcribe(audio, log_result=False)

    def _transcribe(self, audio: np.ndarray, log_result: bool, vad_filter: bool = True) -> str:
        if audio.size == 0:
            return ""
        try:
            segments, info = self._get_model().transcribe(
                audio,
                language=self.settings.language,
                vad_filter=vad_filter,
                beam_size=self.settings.beam_size if log_result else 1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
            )
            # Inference continues while iterating segments; failures there must
            # take the same CPU retry path as failures in language detection.
            text = "".join(segment.text for segment in segments).strip()
        except RuntimeError:
            if self.settings.device != "cuda" or self._using_cpu_fallback:
                raise
            self.logger.exception("CUDA inference failed; retrying this dictation on CPU int8 for this session")
            self._activate_cpu_fallback()
            return self._transcribe(audio, log_result, vad_filter)
        if log_result:
            self.logger.info("Transcript length: %s characters", len(text))
            self.logger.info("Transcribed %0.1fs (%s): %s", audio.size / self.settings.sample_rate,
                             info.language, text[:100])
        return text

    def _activate_cpu_fallback(self) -> None:
        self._using_cpu_fallback = True
        self._model = None
        gc.collect()
        self.settings = replace(self.settings, device="cpu", compute_type="int8")
        # Do not persist a transient CUDA failure. Otherwise one failed start
        # silently turns every later dictation into a much slower CPU job.
        self.logger.warning("CPU fallback is temporary; CUDA will be retried next time the app starts")
