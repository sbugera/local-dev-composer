"""Unit tests for SubprocessInstaller — verifies the log header/footer."""
import pytest

from ldc.application.installer_service import SubprocessInstaller
from ldc.domain.models import InstallConfig


def test_success_log_has_start_and_finish_timestamps(tmp_path):
    log_file = str(tmp_path / "svc-install.log")
    SubprocessInstaller().install(
        service_name="svc",
        config=InstallConfig(command="echo hello"),
        working_dir=str(tmp_path),
        env=None,
        log_file=log_file,
    )
    text = open(log_file, encoding="utf-8").read()

    assert "[LDC] Installing 'svc' at " in text
    assert "[LDC] Finished 'svc' at " in text
    assert "[LDC] Status: SUCCESS — elapsed " in text


def test_failure_records_failed_status_and_raises(tmp_path):
    log_file = str(tmp_path / "svc-install.log")
    installer = SubprocessInstaller()

    with pytest.raises(RuntimeError):
        installer.install(
            service_name="svc",
            config=InstallConfig(command="exit 3"),
            working_dir=str(tmp_path),
            env=None,
            log_file=log_file,
        )

    text = open(log_file, encoding="utf-8").read()
    assert "[LDC] Status: FAILED (exit 3) — elapsed " in text
