import asyncio
import fnmatch
from contextlib import suppress
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whiscraper.browser.page import Page

PROVIVERS_URL_PATTERN = {
    "*challenges.cloudflare.com*": "cloudflare",
}


class CaptchaSolver:
    def __init__(self, page: "Page"):
        self._page = page

    @staticmethod
    @cache
    def _get_providers(url: str) -> str | None:
        for pattern, provider in PROVIVERS_URL_PATTERN.items():
            if fnmatch.fnmatch(url, pattern):
                return provider
        return None

    async def wait_solve(self, sleep: int = 5) -> None:
        await asyncio.sleep(5)
        await self._page.tab
        while True:
            await asyncio.sleep(1)
            with suppress(Exception):
                for script in await self._page.tab.find_all("script", timeout=3):
                    if self._get_providers(script.attrs["src"]):
                        continue
            break

        await self._page.tab
