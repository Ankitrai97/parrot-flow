import json

import pytest

from localdictate.config import Settings
from localdictate.enhancement import TranscriptEnhancer


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_cleanup_stdin_schema_and_safety_flags(monkeypatch, tmp_path, provider):
    from contextlib import contextmanager

    import localdictate.enhancement as module
    @contextmanager
    def directory(**kwargs): yield str(tmp_path)
    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", directory)
    monkeypatch.setattr(module, "executable", lambda name: [name + ".exe"])
    calls = []
    def run(command, prompt, directory, timeout):
        calls.append((command, prompt))
        assert "hey john" not in " ".join(command)
        assert json.loads(prompt.splitlines()[-1]) == {"transcript": "hey john"}
        if provider == "codex":
            assert "--ignore-user-config" in command
            assert "features.shell_tool=false" in command
            assert "read-only" in command
            return json.dumps({"type": "item.completed", "item": {
                "type": "agent_message", "text": '{"text":"Hey John."}'}})
        assert command[command.index("--tools") + 1] == ""
        assert "--strict-mcp-config" in command
        return json.dumps({"is_error": False, "structured_output": {"text": "Hey John."}})
    monkeypatch.setattr(module, "_run", run)
    assert TranscriptEnhancer().enhance("hey john", Settings(enhancement_provider=provider)) == "Hey John."
    assert len(calls) == 1


@pytest.mark.parametrize("response", [{"is_error": True, "result": "Please log in"},
                                      {"structured_output": {"text": ""}},
                                      {"structured_output": {"text": 12}}])
def test_provider_errors_cannot_be_injected_as_transcripts(monkeypatch, tmp_path, response):
    from contextlib import contextmanager

    import localdictate.enhancement as module
    @contextmanager
    def directory(**kwargs): yield str(tmp_path)
    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", directory)
    monkeypatch.setattr(module, "executable", lambda name: ["claude.exe"])
    monkeypatch.setattr(module, "_run", lambda *args: json.dumps(response))
    with pytest.raises((RuntimeError, ValueError)):
        TranscriptEnhancer().enhance("hey john", Settings(enhancement_provider="claude"))


def test_ollama_requires_explicit_local_model():
    with pytest.raises(ValueError, match="installed Ollama"):
        TranscriptEnhancer().enhance("hey john", Settings(enhancement_provider="ollama"))
