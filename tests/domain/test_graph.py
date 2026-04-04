"""Unit tests for the dependency graph and topological sort."""
import pytest

from ldc.domain.exceptions import CircularDependencyError, UnknownServiceError
from ldc.domain.graph import DependencyGraph


def _graph(adj: dict) -> DependencyGraph:
    return DependencyGraph(adj)


class TestStartupOrder:

    def test_no_dependencies(self):
        g = _graph({"a": [], "b": [], "c": []})
        order = g.startup_order(["a", "b", "c"])
        # All three must appear; no ordering constraint
        assert set(order) == {"a", "b", "c"}

    def test_simple_chain(self):
        # a -> b -> c  (a depends on b, b depends on c)
        g = _graph({"a": ["b"], "b": ["c"], "c": []})
        order = g.startup_order(["a"])
        assert order.index("c") < order.index("b") < order.index("a")

    def test_diamond_dependency(self):
        # a -> b, a -> c, b -> d, c -> d
        g = _graph({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        order = g.startup_order(["a"])
        assert order.index("d") < order.index("b")
        assert order.index("d") < order.index("c")
        assert order.index("b") < order.index("a")
        assert order.index("c") < order.index("a")

    def test_circular_dependency_raises(self):
        g = _graph({"a": ["b"], "b": ["a"]})
        with pytest.raises(CircularDependencyError):
            g.startup_order(["a"])

    def test_unknown_service_raises(self):
        g = _graph({"a": []})
        with pytest.raises(UnknownServiceError):
            g.startup_order(["z"])


class TestShutdownOrder:

    def test_shutdown_is_reverse_startup(self):
        g = _graph({"a": ["b"], "b": ["c"], "c": []})
        startup = g.startup_order(["a"])
        shutdown = g.shutdown_order(["a"])
        assert shutdown == list(reversed(startup))


class TestTransitiveDependencies:

    def test_direct_only(self):
        g = _graph({"a": ["b"], "b": [], "c": []})
        deps = g.transitive_dependencies("a")
        assert deps == ["b"]

    def test_deep_chain(self):
        g = _graph({"a": ["b"], "b": ["c"], "c": ["d"], "d": []})
        deps = set(g.transitive_dependencies("a"))
        assert deps == {"b", "c", "d"}
