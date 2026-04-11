from unittest.mock import patch

from ldc.adapters.process.windows_runner import WindowsProcessRunner


class TestResolveExecutable:

    def test_resolves_bare_name_using_service_env_path(self):
        env = {"PATH": "/jdk-21/bin:/usr/bin"}
        with patch("shutil.which", return_value="/jdk-21/bin/java") as mock_which:
            result = WindowsProcessRunner._resolve_executable(["java", "-jar", "app.jar"], env)
        mock_which.assert_called_once_with("java", path="/jdk-21/bin:/usr/bin")
        assert result == ["/jdk-21/bin/java", "-jar", "app.jar"]

    def test_skips_resolution_when_path_separator_present(self):
        parts = ["/jdk-21/bin/java", "-jar", "app.jar"]
        result = WindowsProcessRunner._resolve_executable(parts, {"PATH": "/usr/bin"})
        assert result == parts

    def test_skips_resolution_for_windows_absolute_path(self):
        parts = ["C:\\jdk-21\\bin\\java.exe", "-jar", "app.jar"]
        result = WindowsProcessRunner._resolve_executable(parts, {"PATH": "/usr/bin"})
        assert result == parts

    def test_keeps_original_when_not_found_on_service_path(self):
        with patch("shutil.which", return_value=None):
            result = WindowsProcessRunner._resolve_executable(["java", "-jar", "app.jar"], {"PATH": ""})
        assert result[0] == "java"

    def test_uses_path_case_insensitively(self):
        env = {"Path": "C:/jdk-21/bin"}  # Windows often has 'Path' not 'PATH'
        with patch("shutil.which", return_value="C:/jdk-21/bin/java.exe") as mock_which:
            WindowsProcessRunner._resolve_executable(["java", "-jar", "app.jar"], env)
        mock_which.assert_called_once_with("java", path="C:/jdk-21/bin")
