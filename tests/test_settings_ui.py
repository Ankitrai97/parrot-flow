from dataclasses import asdict

import pytest

from localdictate.config import Settings, load_settings, save_settings
from localdictate.settings_ui import updated_settings


def test_ai_settings_roundtrip_preserves_microphone(tmp_path):
    previous = Settings(microphone_name="Ankit's microphone", language="en")
    values = asdict(previous) | {"enhance_with_llm": True, "enhancement_provider": "claude",
                                "enhancement_model": "", "insertion_mode": "paste"}
    result = updated_settings(previous, values)
    path = tmp_path / "config.toml"
    save_settings(result, path)
    assert load_settings(path) == result
    assert result.microphone_name == previous.microphone_name
    assert result.language == "en"


@pytest.mark.parametrize("field,value", [("enhancement_provider", "shell"), ("beam_size", 8),
                                        ("enhancement_timeout_seconds", 999),
                                        ("enhance_with_llm", "true"), ("insertion_mode", "invalid")])
def test_invalid_settings_rejected(field, value):
    with pytest.raises(ValueError):
        updated_settings(Settings(), asdict(Settings()) | {field: value})
