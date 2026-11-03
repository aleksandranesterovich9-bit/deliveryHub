import asyncio
import contextlib
import signal


def install_shutdown_handlers(stop: asyncio.Event) -> None:
    """Set `stop` on SIGINT/SIGTERM so background processes can finish gracefully.

    `docker compose stop` sends SIGTERM. On Windows signal handlers are not
    supported by asyncio, so there Ctrl+C simply raises KeyboardInterrupt.
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
