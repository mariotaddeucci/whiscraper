import asyncio
from dataclasses import dataclass
from pathlib import Path

import nodriver
from whiscraper.browser.page import Page


@dataclass
class BrowserManagerConfig:
    headless: bool = False
    block_images: bool = True
    mute_audio: bool = True
    max_opened_tabs: int = 1

    def to_browser_config(self):
        browser_config = nodriver.Config()
        browser_config.headless = self.headless

        browser_config.add_argument("--start-maximized")
        browser_config.add_argument("--no-default-browser-check")
        browser_config.add_argument("--no-first-run")

        if self.mute_audio:
            browser_config.add_argument("--mute-audio")

        extensions_dir = Path(__file__).parent / "extensions"
        browser_config.add_extension(str(extensions_dir / "cf-captcha-solver.crx"))
        return browser_config


class BrowserManager:
    def __init__(self, config: BrowserManagerConfig | None = None):
        if config is None:
            config = BrowserManagerConfig()

        self._browser_config = config.to_browser_config()
        self._browser: nodriver.Browser | None = None

        self._lock = asyncio.Lock()

        self._max_opened_tabs = config.max_opened_tabs
        self._max_opened_tabs_exceeded_event = asyncio.Event()

    @property
    def tabs(self) -> list[nodriver.Tab]:
        if self._browser is None:
            return []
        return self._browser.tabs

    async def get_browser(self) -> nodriver.Browser:
        if self._browser is None:
            self._browser = await nodriver.Browser.create(config=self._browser_config)
        return self._browser

    async def new_page(self, url: str = "chrome://welcome") -> Page:
        new_window = len(self.tabs) != 0

        async with self._lock:
            browser = await self.get_browser()
            tab = await browser.get(url=url, new_window=new_window)

        return Page(tab)

    async def close(self):
        async with self._lock:
            for tab in self.tabs:
                await tab.close()

            if self._browser:
                self._browser.stop()

        # await self.close_if_idle()
