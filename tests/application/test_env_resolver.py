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
        assert _parse_env_file(p) == {"FOO": "bar", "BAZ": "qux"}

    def test_quoted_values(self):
        p = self._write('KEY="hello world"\nKEY2=\'single\'\n')
        result = _parse_env_file(p)
        assert result["KEY"] == "hello world"
        assert result["KEY2"] == "single"

    def test_comments_and_blanks(self):
        p = self._write("# comment\n\nFOO=1\n")
        assert _parse_env_file(p) == {"FOO": "1"}

    def test_export_prefix(self):
        p = self._write("export MY_VAR=value\n")
        assert _parse_env_file(p) == {"MY_VAR": "value"}


class TestResolveEnv:

    def test_inline_env_overrides_system(self, monkeypatch):
        monkeypatch.setenv("SHARED_VAR", "from-system")
        result = resolve_env({"SHARED_VAR": "from-inline"}, [], ".")
        assert result["SHARED_VAR"] == "from-inline"

    def test_env_file_merged(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FILE_VAR=from-file\n", encoding="utf-8")
        result = resolve_env({}, [str(env_file)], str(tmp_path))
        assert result["FILE_VAR"] == "from-file"

    def test_inline_wins_over_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("X=from-file\n", encoding="utf-8")
        result = resolve_env({"X": "from-inline"}, [str(env_file)], str(tmp_path))
        assert result["X"] == "from-inline"

    def test_missing_env_file_is_ignored(self):
        result = resolve_env({"K": "v"}, [".nonexistent.env"], ".")
        assert result["K"] == "v"

    def test_multiple_files_last_wins(self, tmp_path):
        f1 = tmp_path / ".env.base"
        f2 = tmp_path / ".env.local"
        f1.write_text("X=base\nA=from-base\n", encoding="utf-8")
        f2.write_text("X=local\n", encoding="utf-8")
        result = resolve_env({}, [str(f1), str(f2)], str(tmp_path))
        assert result["X"] == "local"
        assert result["A"] == "from-base"

    def test_multiple_files_order_matters(self, tmp_path):
        f1 = tmp_path / ".env.1"
        f2 = tmp_path / ".env.2"
        f1.write_text("X=first\n", encoding="utf-8")
        f2.write_text("X=second\n", encoding="utf-8")
        assert resolve_env({}, [str(f1), str(f2)], str(tmp_path))["X"] == "second"
        assert resolve_env({}, [str(f2), str(f1)], str(tmp_path))["X"] == "first"


class TestPathDirs:

    def test_path_dir_prepended(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin")
        result = resolve_env({}, [], ".", ["/custom/bin"])
        entries = result["PATH"].split(os.pathsep)
        assert entries[0] == "/custom/bin"
        assert "/usr/bin" in result["PATH"]

    def test_var_expansion_in_path_dirs(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin")
        result = resolve_env({"JAVA_HOME": "/jdk-21"}, [], ".", ["${JAVA_HOME}/bin"])
        entries = result["PATH"].split(os.pathsep)
        assert entries[0] == "/jdk-21/bin"

    def test_multiple_path_dirs_prepended_in_order(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin")
        result = resolve_env({}, [], ".", ["/first/bin", "/second/bin"])
        entries = result["PATH"].split(os.pathsep)
        assert entries[0] == "/first/bin"
        assert entries[1] == "/second/bin"
        assert "/usr/bin" in result["PATH"]

    def test_no_duplicate_when_already_present(self, monkeypatch):
        monkeypatch.setenv("PATH", "/jdk-21/bin" + os.pathsep + "/usr/bin")
        result = resolve_env({}, [], ".", ["/jdk-21/bin"])
        assert result["PATH"].count("/jdk-21/bin") == 1

    def test_empty_path_dirs_leaves_path_unchanged(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin")
        result = resolve_env({}, [], ".", [])
        assert result["PATH"] == "/usr/bin"

    def test_none_path_dirs_leaves_path_unchanged(self, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin")
        result = resolve_env({}, [], ".")
        assert result["PATH"] == "/usr/bin"
