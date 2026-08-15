from localdictate.config import Settings, load_settings, save_settings


def test_default_settings_prefer_cuda_for_low_latency_dictation():
    settings = Settings()
    assert settings.device == "cuda"
    assert settings.compute_type == "float16"


def test_settings_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    expected = Settings(hotkey="alt+space", language="en", device="cpu", compute_type="int8")
    save_settings(expected, path)
    assert load_settings(path) == expected
