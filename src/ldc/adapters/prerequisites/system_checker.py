"""
Adapter: checks host prerequisites (runtimes, commands, env vars, folders, files, ports).

Every check produces a CheckResult with a human-readable fix_hint so the
user always knows exactly what to do when something is missing.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from ldc.domain.models import CheckResult, Prerequisites, PrerequisiteReport
from ldc.ports.prerequisite_checker import IPrerequisiteChecker


class SystemPrerequisiteChecker(IPrerequisiteChecker):

    def check(self, service_name: str, prereqs: Prerequisites) -> PrerequisiteReport:
        results: List[CheckResult] = []

        if prereqs.java:
            results.append(self._check_runtime("java", prereqs.java))
        if prereqs.python:
            results.append(self._check_runtime("python", prereqs.python))
        if prereqs.node:
            results.append(self._check_runtime("node", prereqs.node))
        if prereqs.dotnet:
            results.append(self._check_runtime("dotnet", prereqs.dotnet))

        for cmd in prereqs.commands:
            results.append(self._check_command(cmd))

        for var in prereqs.env_vars:
            results.append(self._check_env_var(var))

        for folder in prereqs.folders:
            results.append(self._check_folder(folder))

        for filepath in prereqs.files:
            results.append(self._check_file(filepath))

        for port in prereqs.ports_free:
            results.append(self._check_port_free(port))

        return PrerequisiteReport(service_name=service_name, checks=results)

    def auto_fix(self, service_name: str, prereqs: Prerequisites) -> PrerequisiteReport:
        """Only auto-fixable action: create missing folders."""
        for folder in prereqs.folders:
            try:
                Path(folder).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        return self.check(service_name, prereqs)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_runtime(self, runtime: str, constraint: str) -> CheckResult:
        binary_map = {
            "java": ("java", "-version"),
            "python": ("python", "--version"),
            "node": ("node", "--version"),
            "dotnet": ("dotnet", "--version"),
        }
        binary, flag = binary_map[runtime]
        installed_ver = self._get_version(binary, flag)

        if installed_ver is None:
            return CheckResult(
                name=f"{runtime} runtime",
                passed=False,
                message=f"'{binary}' not found on PATH",
                fix_hint=self._runtime_install_hint(runtime),
            )

        satisfied, reason = self._version_satisfies(installed_ver, constraint)
        return CheckResult(
            name=f"{runtime} runtime",
            passed=satisfied,
            message=f"{runtime} {installed_ver} — required: {constraint}",
            fix_hint=None if satisfied else self._runtime_install_hint(runtime),
        )

    def _check_command(self, cmd: str) -> CheckResult:
        found = shutil.which(cmd) is not None
        return CheckResult(
            name=f"command '{cmd}'",
            passed=found,
            message=f"'{cmd}' {'found on PATH' if found else 'NOT found on PATH'}",
            fix_hint=(
                None
                if found
                else f"Install '{cmd}' and ensure it is on your PATH. "
                     f"On Windows you can check: where {cmd}"
            ),
        )

    def _check_env_var(self, var: str) -> CheckResult:
        value = os.environ.get(var)
        present = value is not None and value.strip() != ""
        return CheckResult(
            name=f"env var '{var}'",
            passed=present,
            message=f"${var} {'is set' if present else 'is NOT set'}",
            fix_hint=(
                None
                if present
                else f"Set the environment variable: setx {var} \"<value>\" "
                     f"(system-wide) or add it to your .env file"
            ),
        )

    def _check_folder(self, folder: str) -> CheckResult:
        path = Path(folder)
        exists = path.exists() and path.is_dir()
        return CheckResult(
            name=f"folder '{folder}'",
            passed=exists,
            message=f"'{folder}' {'exists' if exists else 'does NOT exist'}",
            fix_hint=(
                None
                if exists
                else f"Create the folder: mkdir -p \"{folder}\"  "
                     f"(or run: ldc check --fix to auto-create)"
            ),
        )

    def _check_file(self, filepath: str) -> CheckResult:
        path = Path(filepath)
        exists = path.exists() and path.is_file()
        return CheckResult(
            name=f"file '{filepath}'",
            passed=exists,
            message=f"'{filepath}' {'exists' if exists else 'does NOT exist'}",
            fix_hint=(
                None
                if exists
                else f"Create or copy the required file to: {filepath}"
            ),
        )

    def _check_port_free(self, port: int) -> CheckResult:
        in_use = self._is_port_in_use(port)
        return CheckResult(
            name=f"port {port} free",
            passed=not in_use,
            message=f"Port {port} is {'in use' if in_use else 'free'}",
            fix_hint=(
                None
                if not in_use
                else f"Port {port} is occupied. Find the process: "
                     f"netstat -ano | findstr :{port}  "
                     f"then terminate it or change the service port."
            ),
        )

    # ------------------------------------------------------------------
    # Version utilities
    # ------------------------------------------------------------------

    def _get_version(self, binary: str, flag: str) -> Optional[str]:
        try:
            result = subprocess.run(
                [binary, flag],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # java -version prints to stderr; others to stdout
            output = (result.stdout + result.stderr).strip()
            return self._extract_version(output)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None

    _VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")

    def _extract_version(self, text: str) -> Optional[str]:
        m = self._VERSION_RE.search(text)
        if not m:
            return None
        parts = [m.group(i) or "0" for i in (1, 2, 3)]
        return ".".join(parts)

    def _version_satisfies(
        self, installed: str, constraint: str
    ) -> Tuple[bool, str]:
        """Evaluate simple constraints like '>=17', '>11', '==3.9'."""
        m = re.match(r"^(>=|>|<=|<|==)(\d+(?:\.\d+)?(?:\.\d+)?)$", constraint.strip())
        if not m:
            return True, "unparseable constraint — skipped"

        op, required_str = m.group(1), m.group(2)
        inst_tuple = self._ver_tuple(installed)
        req_tuple = self._ver_tuple(required_str)

        ops = {
            ">=": inst_tuple >= req_tuple,
            ">": inst_tuple > req_tuple,
            "<=": inst_tuple <= req_tuple,
            "<": inst_tuple < req_tuple,
            "==": inst_tuple == req_tuple,
        }
        satisfied = ops[op]
        return satisfied, f"{installed} {op} {required_str}"

    @staticmethod
    def _ver_tuple(ver: str) -> tuple:
        parts = ver.split(".")
        result = []
        for p in parts[:3]:
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        while len(result) < 3:
            result.append(0)
        return tuple(result)

    @staticmethod
    def _is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    @staticmethod
    def _runtime_install_hint(runtime: str) -> str:
        hints = {
            "java": (
                "Install JDK and add JAVA_HOME to system env vars. "
                "Download from: https://adoptium.net  "
                "Then: setx JAVA_HOME \"C:\\Program Files\\Eclipse Adoptium\\jdk-XX\""
            ),
            "python": (
                "Install Python from https://python.org/downloads "
                "and ensure 'Add Python to PATH' is checked during setup."
            ),
            "node": (
                "Install Node.js from https://nodejs.org "
                "and ensure the installer adds it to PATH."
            ),
            "dotnet": (
                "Install .NET SDK from https://dotnet.microsoft.com/download "
                "and restart your terminal."
            ),
        }
        return hints.get(runtime, f"Install '{runtime}' and add it to PATH.")
