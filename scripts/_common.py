"""Shared bootstrap for the command-line scripts: settings, logging and a started service layer."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services import Services  # noqa: E402


def run(main):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())


async def services(seed: bool = True) -> Services:
    s = Services(get_settings())
    s.settings.seed_on_start = seed
    await s.start()
    return s
