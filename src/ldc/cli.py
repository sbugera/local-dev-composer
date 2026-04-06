#!/usr/bin/env python3
"""
ldc — Local Dev Composer
========================
Orchestrate local microservice environments without Docker or WSL.

Usage examples
--------------
  ldc clone                          # clone all repos
  ldc clone gateway user-service     # clone specific services
  ldc clone --pull                   # pull latest on already-cloned repos

  ldc check                          # check prerequisites for all services
  ldc check gateway --fix            # check and auto-fix (create folders, etc.)

  ldc install                        # run install commands for all services
  ldc install user-service           # install one service

  ldc up                             # start all services in dependency order
  ldc up --group my-service          # start a named group + its dependencies
  ldc up gateway user-service        # start specific services + their deps
  ldc up --skip-checks               # skip prerequisite checks on startup

  ldc down                           # stop all services
  ldc down gateway                   # stop one service

  ldc status                         # show current status table
  ldc logs gateway                   # show last 50 lines of gateway log
  ldc logs gateway -f                # follow (tail -f) gateway log

  ldc doctor                         # full diagnostic with actionable fix hints
"""

import argparse
import sys
from pathlib import Path

from ldc.application.container import Container


def _find_config(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        print(f"Error: config file not found: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ldc",
        description="Local Dev Composer — orchestrate microservice environments locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-f", "--file",
        default="composer.yml",
        metavar="FILE",
        help="Path to composer.yml (default: ./composer.yml)",
    )
    parser.add_argument(
        "--ldc-dir",
        default=".ldc",
        metavar="DIR",
        help="Directory for state and logs (default: .ldc)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Max parallel workers for clone/install/up (overrides composer.yml; default: 4)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ---- bootstrap ----
    p_bootstrap = sub.add_parser("bootstrap", help="Clone, install, and start all services")
    p_bootstrap.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_bootstrap.add_argument("-g", "--group", metavar="GROUP", help="Bootstrap a named group")
    p_bootstrap.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")

    # ---- clone ----
    p_clone = sub.add_parser("clone", help="Clone or update service repositories")
    p_clone.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_clone.add_argument("--pull", action="store_true", help="Pull if already cloned")

    # ---- check ----
    p_check = sub.add_parser("check", help="Check host prerequisites")
    p_check.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_check.add_argument("--fix", action="store_true", help="Auto-fix where possible")

    # ---- install ----
    p_install = sub.add_parser("install", help="Run install commands")
    p_install.add_argument("services", nargs="*", help="Service names (all if omitted)")

    # ---- up ----
    p_up = sub.add_parser("up", help="Start services in dependency order")
    p_up.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_up.add_argument("-g", "--group", metavar="GROUP", help="Start a named group")
    p_up.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")

    # ---- down ----
    p_down = sub.add_parser("down", help="Stop services")
    p_down.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_down.add_argument("--timeout", type=int, default=15, metavar="SEC")

    # ---- status ----
    p_status = sub.add_parser("status", help="Show service status table")
    p_status.add_argument("services", nargs="*")

    # ---- logs ----
    p_logs = sub.add_parser("logs", help="View service logs")
    p_logs.add_argument("service", help="Service name")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow (tail -f)")
    p_logs.add_argument("-n", "--tail", type=int, default=50, metavar="N",
                        help="Number of lines to show (default: 50)")

    # ---- env ----
    p_env = sub.add_parser("env", help="Show resolved environment variables for a service")
    p_env.add_argument("service", help="Service name")
    p_env.add_argument("--all", dest="show_inherited", action="store_true",
                       help="Include inherited system variables")
    p_env.add_argument("--filter", metavar="PREFIX", dest="filter_prefix",
                       help="Only show variables starting with PREFIX")

    # ---- restart ----
    p_restart = sub.add_parser("restart", help="Stop then start services (no install)")
    p_restart.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_restart.add_argument("-g", "--group", metavar="GROUP", help="Restart a named group")
    p_restart.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")

    # ---- rebuild ----
    p_rebuild = sub.add_parser("rebuild", help="Stop, install, then start services")
    p_rebuild.add_argument("services", nargs="*", help="Service names (all if omitted)")
    p_rebuild.add_argument("-g", "--group", metavar="GROUP", help="Rebuild a named group")
    p_rebuild.add_argument("--skip-checks", action="store_true", help="Skip prerequisite checks")

    # ---- doctor ----
    p_doctor = sub.add_parser("doctor", help="Full diagnostic with fix suggestions")
    p_doctor.add_argument("services", nargs="*")

    args = parser.parse_args()

    config_path = _find_config(args.file)
    config_dir = str(config_path.parent)
    container = Container(ldc_dir=Path(args.ldc_dir))
    config = container.config_reader.read(config_path)

    # CLI --workers overrides composer.yml workers; composer.yml overrides built-in default
    workers = args.workers if args.workers is not None else config.workers

    # ------------------------------------------------------------------
    if args.command == "bootstrap":
        container.bootstrap_cmd.execute(
            config,
            service_names=args.services or None,
            group_name=args.group,
            skip_checks=args.skip_checks,
            config_dir=config_dir,
            workers=workers,
        )

    elif args.command == "clone":
        container.clone_cmd.execute(
            config,
            service_names=args.services or None,
            pull=args.pull,
            workers=workers,
        )

    elif args.command == "check":
        ok = container.check_cmd.execute(
            config,
            service_names=args.services or None,
            auto_fix=args.fix,
        )
        sys.exit(0 if ok else 1)

    elif args.command == "install":
        container.install_cmd.execute(
            config,
            service_names=args.services or None,
            config_dir=config_dir,
            workers=workers,
        )

    elif args.command == "up":
        container.up_cmd.execute(
            config,
            service_names=args.services or None,
            group_name=args.group,
            skip_checks=args.skip_checks,
            config_dir=config_dir,
            workers=workers,
        )

    elif args.command == "down":
        container.down_cmd.execute(
            config,
            service_names=args.services or None,
            timeout_seconds=args.timeout,
        )

    elif args.command == "status":
        container.status_cmd.execute(
            config,
            service_names=args.services or None,
        )

    elif args.command == "logs":
        container.logs_cmd.execute(
            config,
            service_name=args.service,
            follow=args.follow,
            tail=args.tail,
        )

    elif args.command == "env":
        container.env_cmd.execute(
            config,
            service_name=args.service,
            config_dir=config_dir,
            show_inherited=args.show_inherited,
            filter_prefix=args.filter_prefix,
        )

    elif args.command == "restart":
        container.restart_cmd.execute(
            config,
            service_names=args.services or None,
            group_name=args.group,
            skip_checks=args.skip_checks,
            config_dir=config_dir,
            workers=workers,
        )

    elif args.command == "rebuild":
        if not args.services and not args.group:
            answer = input("Rebuild ALL services? This will stop, reinstall, and restart everything. [y/N] ")
            if answer.strip().lower() != "y":
                print("Aborted.")
                sys.exit(0)
        container.rebuild_cmd.execute(
            config,
            service_names=args.services or None,
            group_name=args.group,
            skip_checks=args.skip_checks,
            config_dir=config_dir,
            workers=workers,
        )

    elif args.command == "doctor":
        container.doctor_cmd.execute(
            config,
            service_names=args.services or None,
        )
