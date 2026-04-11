import pytest

from ldc.adapters.prerequisites.system_checker import SystemPrerequisiteChecker


@pytest.fixture
def checker():
    return SystemPrerequisiteChecker()


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
