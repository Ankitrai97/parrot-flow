from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import re
import tomllib


@dataclass(frozen=True)
class Settings:
    hotkey: str = "ctrl+windows"
    microphone: int | None = None
    model: str = "small"
    # CUDA FP16 is the right default for the RTX 3050 in this machine. It
    # keeps the small Whisper model responsive enough for interactive use.
    device: str = "cuda"
    compute_type: str = "float16"
    language: str | None = None
    sample_rate: int = 16_000
    silence_threshold: float = 0.002
    trim_silence_seconds: float = 0.35
    auto_stop_seconds: float = 4.0
    hotkey_mode: str = "toggle"
    live_preview: bool = True
    live_preview_interval_seconds: float = 1.5
    live_preview_window_seconds: float = 8.0
    auto_stop_on_silence: bool = False
    enhance_with_llm: bool = False
    start_with_windows: bool = False


def config_path() -> Path:
    app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(app_data) / "LocalDictate" / "config.toml"


def load_settings(path: Path | None = None) -> Settings:
    path = path or config_path()
    if not path.exists():
        save_settings(Settings(), path)
        return Settings()
    content = path.read_text(encoding="utf-8")
    try:
        raw = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        # Versions before 0.1.1 wrote Python's `None`, which TOML does not
        # support. Omitted optional settings correctly resolve to dataclass
        # defaults, so repair that single legacy representation in place.
        repaired = re.sub(r"(?m)^\w+\s*=\s*None\s*\r?\n?", "", content)
        if repaired == content:
            raise
        raw = tomllib.loads(repaired)
        path.write_text(repaired, encoding="utf-8")
    valid = {key: value for key, value in raw.items() if key in Settings.__dataclass_fields__}
    return Settings(**valid)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in asdict(settings).items():
        if value is None:
            continue
        rendered = "true" if value is True else "false" if value is False else repr(value)
        lines.append(f"{key} = {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
