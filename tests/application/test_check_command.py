"""Unit tests for CheckCommand — uses a mock prerequisite checker."""
from unittest.mock import MagicMock

from ldc.application.commands.check import CheckCommand
from ldc.domain.models import (
    CheckResult,
    Prerequisites,
    PrerequisiteReport,
    Runtime,
    Service,
    WorkspaceConfig,
)


def _make_config(*service_names: str, with_prereqs: bool = True) -> WorkspaceConfig:
    services = {}
    for name in service_names:
        services[name] = Service(
            name=name,
            runtime=Runtime.JAVA,
            requires=Prerequisites(java=">=17") if with_prereqs else None,
        )
    return WorkspaceConfig(root="./services", services=services)


class TestCheckCommand:

    def _cmd(self, report: PrerequisiteReport):
        checker = MagicMock()
        checker.check.return_value = report
        checker.auto_fix.return_value = report
        reporter = MagicMock()
        return CheckCommand(checker, reporter), checker, reporter

    def test_returns_true_when_all_pass(self):
        report = PrerequisiteReport(
            service_name="svc",
            checks=[CheckResult("java runtime", True, "java 17.0.0")],
        )
        cmd, _, _ = self._cmd(report)
        config = _make_config("svc")
        result = cmd.execute(config)
        assert result is True

    def test_returns_false_when_check_fails(self):
        report = PrerequisiteReport(
            service_name="svc",
            checks=[
                CheckResult("java runtime", False, "java not found", "Install JDK")
            ],
        )
        cmd, _, _ = self._cmd(report)
        config = _make_config("svc")
        result = cmd.execute(config)
        assert result is False

    def test_skips_service_with_no_prereqs(self):
        cmd, checker, _ = self._cmd(MagicMock())
        config = _make_config("svc", with_prereqs=False)
        cmd.execute(config)
        checker.check.assert_not_called()

    def test_calls_auto_fix_when_flagged(self):
        report = PrerequisiteReport(service_name="svc", checks=[])
        cmd, checker, _ = self._cmd(report)
        config = _make_config("svc")
        cmd.execute(config, auto_fix=True)
        checker.auto_fix.assert_called_once()
        checker.check.assert_not_called()
