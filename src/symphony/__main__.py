"""CLI entry point — signal handlers, graceful shutdown (PRD §14)."""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from symphony.config import ConfigError, build_config
from symphony.log import get_logger, setup_logging
from symphony.orchestrator import Orchestrator
from symphony.workflow import load_workflow


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="symphony",
        description="Symphony — orchestrate Codex agents from Linear issues",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        default="./WORKFLOW.md",
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    return parser


async def _run(workflow_path: str) -> int:
    log = get_logger()
    try:
        wf = load_workflow(workflow_path)
    except FileNotFoundError:
        log.error("symphony.cli.workflow_not_found", path=workflow_path)
        return 2
    except ValueError as exc:
        log.error("symphony.cli.workflow_invalid", error=str(exc))
        return 2

    try:
        config = build_config(wf.config)
    except ConfigError as exc:
        log.error("symphony.cli.config_error", error=str(exc))
        return 2

    orch = Orchestrator(config=config, workflow=wf)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(orch.shutdown()))
        except NotImplementedError:
            # add_signal_handler is unavailable on Windows event loops.
            signal.signal(sig, lambda *_: asyncio.create_task(orch.shutdown()))

    await orch.run_forever()
    return 0


def main() -> None:
    setup_logging()
    parser = _build_arg_parser()
    args = parser.parse_args()

    exit_code = asyncio.run(_run(args.workflow))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
