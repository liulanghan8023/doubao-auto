from __future__ import annotations

import asyncio
import logging
import signal

from doubao_automation.config import Settings
from doubao_automation.runner import run_once

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        logger.info("Stop signal received.")
        self._stop_event.set()

    async def serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                await run_once(self.settings)
            except Exception:
                logger.exception("Worker iteration failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.interval_seconds,
                )
            except asyncio.TimeoutError:
                continue


def install_signal_handlers(worker: Worker) -> None:
    def _handler(signum: int, _frame: object) -> None:
        logger.info("Handling signal %s", signum)
        worker.request_stop()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

