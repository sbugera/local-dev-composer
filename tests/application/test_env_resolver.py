"""Unit tests for per-service environment resolution."""
import os
import tempfile
from pathlib import Path

from ldc.application.env_resolver import resolve_env, _parse_env_file


class TestParseEnvFile:

    def _write(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return Path(f.name)

    def test_basic_key_value(self):
        p = self._write("FOO=bar\nBAZ=qux\n")
        result = _parse_env_file(p)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_quoted_values(self):
        p = self._write('KEY="hello world"\nKEY2=\'single\'\n')
        result = _parse_env_file(p)
        assert result["KEY"] == "hello world"
        assert result["KEY2"] == "single"

    def test_comments_and_blanks(self):
        p = self._write("# comment\n\nFOO=1\n")
        result = _parse_env_file(p)
        assert result == {"FOO": "1"}

    def test_export_prefix(self):
        p = self._write("export MY_VAR=value\n")
        result = _parse_env_file(p)
        assert result == {"MY_VAR": "value"}


class TestResolveEnv:

    def test_inline_env_overrides_system(self, monkeypatch):
        monkeypatch.setenv("SHARED_VAR", "from-system")
        result = resolve_env({"SHARED_VAR": "from-inline"}, None, ".")
        assert result["SHARED_VAR"] == "from-inline"

    def test_env_file_merged(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FILE_VAR=from-file\n", encoding="utf-8")
        result = resolve_env({}, str(env_file), str(tmp_path))
        assert result["FILE_VAR"] == "from-file"

    def test_inline_wins_over_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("X=from-file\n", encoding="utf-8")
        result = resolve_env({"X": "from-inline"}, str(env_file), str(tmp_path))
        assert result["X"] == "from-inline"

    def test_missing_env_file_is_ignored(self):
        result = resolve_env({"K": "v"}, ".nonexistent.env", ".")
        assert result["K"] == "v"
