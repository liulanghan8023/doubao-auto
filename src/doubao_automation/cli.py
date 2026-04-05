from __future__ import annotations

import argparse
import asyncio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playwright automation scaffold")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("login", help="Open a browser for manual login and save session")
    subparsers.add_parser("once", help="Run the automation task once")
    subparsers.add_parser("web", help="Run the web control panel")
    subparsers.add_parser("worker", help="Run the automation task in a loop")

    return parser


async def _run_worker() -> None:
    from doubao_automation.config import load_settings
    from doubao_automation.logging import configure_logging
    from doubao_automation.worker import Worker, install_signal_handlers

    settings = load_settings()
    configure_logging(settings.log_level)
    worker = Worker(settings)
    install_signal_handlers(worker)
    await worker.serve()


async def _run_once() -> None:
    from doubao_automation.config import load_settings
    from doubao_automation.logging import configure_logging
    from doubao_automation.runner import run_once

    settings = load_settings()
    configure_logging(settings.log_level)
    await run_once(settings)


async def _run_login() -> None:
    from doubao_automation.config import load_settings
    from doubao_automation.logging import configure_logging
    from doubao_automation.runner import ensure_login

    settings = load_settings()
    configure_logging(settings.log_level)
    await ensure_login(settings)


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "web":
        from doubao_automation.web import run_web_server

        run_web_server()
        return

    if args.command == "login":
        asyncio.run(_run_login())
        return

    if args.command == "once":
        asyncio.run(_run_once())
        return

    if args.command == "worker":
        asyncio.run(_run_worker())
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
