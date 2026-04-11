from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ldc.adapters.prerequisites.system_checker import SystemPrerequisiteChecker


@pytest.fixture
def checker():
    return SystemPrerequisiteChecker()


def _fake_run(version_output: str):
    """Return a mock subprocess.run result that reports the given version string."""
    result = MagicMock()
    result.stdout = ""
    result.stderr = version_output
    return result


class TestVersionSatisfies:

    @pytest.mark.parametrize("installed,constraint,expected", [
        # == major only — any subversion of that major passes
        ("17.0.17",  "==17",    True),
        ("17.0.18",  "==17",    True),
        ("17.99.99", "==17",    True),
        ("21.0.10",  "==17",    False),
        ("11.0.0",   "==17",    False),
        # == major.minor — any patch passes
        ("17.0.1",   "==17.0",  True),
        ("17.0.99",  "==17.0",  True),
        ("17.1.0",   "==17.0",  False),
        ("21.0.0",   "==17.0",  False),
        # == exact
        ("17.0.1",   "==17.0.1", True),
        ("17.0.2",   "==17.0.1", False),
        ("17.1.0",   "==17.0.1", False),
        # >= / >
        ("21.0.10",  ">=17",    True),
        ("17.0.0",   ">=17",    True),
        ("11.0.0",   ">=17",    False),
        ("18.0.0",   ">17",     True),
        ("17.0.0",   ">17",     False),
        # <= / <
        ("11.0.0",   "<=17",    True),
        ("17.0.0",   "<=17",    True),
        ("21.0.0",   "<=17",    False),
        ("16.9.9",   "<17",     True),
        ("17.0.0",   "<17",     False),
        # unparseable — skipped (pass)
        ("17.0.0",   "latest",  True),
        ("17.0.0",   "",        True),
    ])
    def test_version_satisfies(self, checker, installed, constraint, expected):
        satisfied, _ = checker._version_satisfies(installed, constraint)
        assert satisfied == expected


class TestCheckRuntimeWithEnv:

    def test_uses_java_home_binary_when_set(self, checker):
        env = {"JAVA_HOME": "C:/jdk-17"}
        with patch("subprocess.run", return_value=_fake_run('openjdk version "17.0.5"')) as mock_run:
            checker._check_runtime("java", "==17", env)
        called_binary = mock_run.call_args[0][0][0]
        assert called_binary == str(Path("C:/jdk-17") / "bin" / "java")

    def test_uses_node_home_binary_when_set(self, checker):
        env = {"NODE_HOME": "C:/node-20"}
        with patch("subprocess.run", return_value=_fake_run("v20.11.0")) as mock_run:
            checker._check_runtime("node", "==20", env)
        called_binary = mock_run.call_args[0][0][0]
        assert called_binary == str(Path("C:/node-20") / "bin" / "node")

    def test_uses_default_binary_when_home_not_set(self, checker):
        with patch("subprocess.run", return_value=_fake_run('openjdk version "17.0.5"')) as mock_run:
            checker._check_runtime("java", "==17", None)
        called_binary = mock_run.call_args[0][0][0]
        assert called_binary == "java"

    def test_env_passed_to_subprocess(self, checker):
        env = {"JAVA_HOME": "C:/jdk-17", "PATH": "/custom/bin"}
        with patch("subprocess.run", return_value=_fake_run('openjdk version "17.0.5"')) as mock_run:
            checker._check_runtime("java", ">=17", env)
        assert mock_run.call_args[1]["env"] == env

    def test_fix_hint_mentions_java_home_when_binary_missing(self, checker):
        env = {"JAVA_HOME": "C:/jdk-17"}
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = checker._check_runtime("java", "==17", env)
        assert not result.passed
        assert "JAVA_HOME" in result.fix_hint
        assert "C:/jdk-17" in result.fix_hint

    def test_version_constraint_applied_against_home_binary(self, checker):
        env = {"JAVA_HOME": "C:/jdk-21"}
        with patch("subprocess.run", return_value=_fake_run('openjdk version "21.0.3"')):
            result = checker._check_runtime("java", "==17", env)
        assert not result.passed

        with patch("subprocess.run", return_value=_fake_run('openjdk version "21.0.3"')):
            result = checker._check_runtime("java", "==21", env)
        assert result.passed


class TestExtractVersion:

    def test_ignores_java_tool_options_line(self, checker):
        output = "Picked up JAVA_TOOL_OPTIONS: -Xms512m -Xmx1024m\nopenjdk version \"21.0.3\" 2024-01-16 LTS"
        assert checker._extract_version(output) == "21.0.3"

    def test_ignores_java_options_line(self, checker):
        output = "Picked up _JAVA_OPTIONS: -Xmx512m\nopenjdk version \"17.0.5\" 2022-10-18 LTS"
        assert checker._extract_version(output) == "17.0.5"

    def test_plain_version_still_parsed(self, checker):
        assert checker._extract_version('openjdk version "21.0.3"') == "21.0.3"
