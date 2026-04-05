"""
Dependency graph and topological sort for service startup ordering.
Pure domain logic — no I/O, no external dependencies.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set

from ldc.domain.exceptions import CircularDependencyError, UnknownServiceError


class DependencyGraph:
    """
    Directed acyclic graph of service dependencies.

    An edge  A → B  means "A depends on B" (B must start before A).
    """

    def __init__(self, adjacency: Dict[str, List[str]]) -> None:
        self._adj = adjacency  # name -> [dependency names]
        self._all_names: Set[str] = set(adjacency.keys())

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_services(cls, services: Dict[str, "Service"]) -> "DependencyGraph":  # noqa: F821
        from ldc.domain.models import Service  # local import to avoid circular

        adjacency: Dict[str, List[str]] = {}
        all_names = set(services.keys())

        for name, svc in services.items():
            for dep in svc.depends_on:
                if dep not in all_names:
                    raise UnknownServiceError(
                        f"Service '{name}' depends on unknown service '{dep}'"
                    )
            adjacency[name] = list(svc.depends_on)

        return cls(adjacency)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def transitive_dependencies(self, name: str) -> List[str]:
        """Return all services that *name* transitively depends on (excluding itself)."""
        if name not in self._all_names:
            raise UnknownServiceError(f"Unknown service: '{name}'")

        visited: Set[str] = set()
        order: List[str] = []

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for dep in self._adj.get(node, []):
                dfs(dep)
            if node != name:
                order.append(node)

        dfs(name)
        return order

    def startup_order(self, names: List[str]) -> List[str]:
        """
        Return a valid startup order (leaf dependencies first) for the given
        set of service names, including their transitive dependencies.

        Raises CircularDependencyError if a cycle is detected.
        """
        # Expand to include all transitive deps
        expanded: Set[str] = set()
        for n in names:
            expanded.add(n)
            expanded.update(self.transitive_dependencies(n))

        # Kahn's algorithm on the sub-graph
        in_degree: Dict[str, int] = {n: 0 for n in expanded}
        reverse_adj: Dict[str, List[str]] = defaultdict(list)

        for node in expanded:
            for dep in self._adj.get(node, []):
                if dep in expanded:
                    in_degree[node] += 1
                    reverse_adj[dep].append(node)

        queue: deque[str] = deque(n for n in expanded if in_degree[n] == 0)
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for dependent in reverse_adj[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(expanded):
            cycle_nodes = expanded - set(order)
            raise CircularDependencyError(
                f"Circular dependency detected among: {sorted(cycle_nodes)}"
            )

        return order

    def shutdown_order(self, names: List[str]) -> List[str]:
        """Reverse of startup_order — dependents are stopped before dependencies."""
        return list(reversed(self.startup_order(names)))

    def shutdown_order_explicit(self, names: List[str]) -> List[str]:
        """
        Stop exactly *names* in safe order (dependents before dependencies),
        without expanding to transitive dependencies.
        """
        name_set = set(names)
        in_degree: Dict[str, int] = {n: 0 for n in name_set}
        reverse_adj: Dict[str, List[str]] = defaultdict(list)

        for node in name_set:
            for dep in self._adj.get(node, []):
                if dep in name_set:
                    in_degree[node] += 1
                    reverse_adj[dep].append(node)

        queue: deque[str] = deque(n for n in name_set if in_degree[n] == 0)
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for dependent in reverse_adj[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        return list(reversed(order))

    def dependents_of(self, name: str) -> List[str]:
        """Return services that directly depend on *name*."""
        return [n for n, deps in self._adj.items() if name in deps]

    @property
    def all_names(self) -> Set[str]:
        return set(self._all_names)
