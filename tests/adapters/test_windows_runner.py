from unittest.mock import patch

from ldc.adapters.process.windows_runner import WindowsProcessRunner
from ldc.domain.models import ServiceState, ServiceStatus


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


class TestWriteFooter:

    def test_writes_status_and_elapsed(self, tmp_path):
        log_file = tmp_path / "svc.log"
        log_file.write_text("[LDC] Starting 'svc'...\n", encoding="utf-8")
        state = ServiceState(
            name="svc",
            status=ServiceStatus.HEALTHY,
            log_file=str(log_file),
            started_at="2026-06-18T10:00:00+00:00",
        )

        WindowsProcessRunner._write_footer(state, "STOPPED")

        text = log_file.read_text(encoding="utf-8")
        assert "[LDC] Stopped 'svc' at " in text
        assert "[LDC] Status: STOPPED — elapsed " in text

    def test_omits_elapsed_when_no_start_time(self, tmp_path):
        log_file = tmp_path / "svc.log"
        log_file.write_text("", encoding="utf-8")
        state = ServiceState(name="svc", status=ServiceStatus.STOPPED, log_file=str(log_file))

        WindowsProcessRunner._write_footer(state, "EXITED (process already gone)")

        text = log_file.read_text(encoding="utf-8")
        assert "[LDC] Status: EXITED (process already gone)\n" in text
        assert "elapsed" not in text

    def test_noop_when_no_log_file(self):
        state = ServiceState(name="svc", status=ServiceStatus.STOPPED, log_file=None)
        WindowsProcessRunner._write_footer(state, "STOPPED")  # must not raise


class TestNoteExit:

    def _runner(self):
        from unittest.mock import MagicMock

        from ldc.ports.state_store import IStateStore

        store = MagicMock(spec=IStateStore)
        store.load.return_value = {}
        return WindowsProcessRunner(store)

    def test_writes_crash_footer_and_clears_pid(self, tmp_path):
        log_file = tmp_path / "svc.log"
        log_file.write_text("", encoding="utf-8")
        state = ServiceState(
            name="svc",
            status=ServiceStatus.FAILED,
            pid=4321,
            log_file=str(log_file),
            started_at="2026-06-18T10:00:00+00:00",
        )
        runner = self._runner()

        runner.note_exit(state)

        assert state.pid is None
        text = log_file.read_text(encoding="utf-8")
        assert "[LDC] Status: CRASHED (process exited) — elapsed " in text

    def test_idempotent_does_not_write_twice(self, tmp_path):
        log_file = tmp_path / "svc.log"
        log_file.write_text("", encoding="utf-8")
        state = ServiceState(
            name="svc", status=ServiceStatus.FAILED, pid=4321, log_file=str(log_file)
        )
        runner = self._runner()

        runner.note_exit(state)
        runner.note_exit(state)  # pid already cleared — must be a no-op

        text = log_file.read_text(encoding="utf-8")
        assert text.count("[LDC] Stopped 'svc'") == 1
