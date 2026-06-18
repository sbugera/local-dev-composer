"""Regression test: the log view must not parse service output as Rich markup.

Service log lines routinely contain '[...]' (thread names like
'[worker-1]', collections like '[ROLE_A]', stray HTML tags like
'[/page.html]'). With markup enabled the RichLog garbled them and
crashed with MarkupError, so the log view is created with markup=False.
"""
from unittest.mock import MagicMock

import pytest
from textual.widgets import RichLog

from ldc.adapters.reporting.interactive_app import LdcInteractiveApp
from ldc.domain.models import WorkspaceConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_app() -> LdcInteractiveApp:
    # Empty services keeps on_mount from touching the (mocked) container.
    config = WorkspaceConfig(root=".", services={})
    return LdcInteractiveApp(
        container=MagicMock(),
        config=config,
        reporter=MagicMock(),
    )


@pytest.mark.anyio
async def test_log_view_has_markup_disabled():
    app = _make_app()
    async with app.run_test():
        log_widget = app.query_one("#log-view", RichLog)
        assert log_widget.markup is False


@pytest.mark.anyio
async def test_log_view_renders_bracketed_lines_without_error():
    app = _make_app()
    async with app.run_test() as pilot:
        log_widget = app.query_one("#log-view", RichLog)
        # The exact shape that previously raised MarkupError.
        log_widget.write(
            "2026-06-12T12:17:33 ERROR 4332 --- [worker-1] "
            "com.example.app.Service : redirect to [/page.html]"
        )
        log_widget.write("permissions - [ROLE_A, ROLE_B]")
        await pilot.pause()  # let the widget render; would surface a crash
