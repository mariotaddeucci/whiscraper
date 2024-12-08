import asyncio

import nodriver

from .page import Page


class BrowserManager:
    def __init__(
        self,
        browser_config: nodriver.Config | None = None,
        headless: bool = False,
        block_images: bool = True,
        mute_audio: bool = True,
        max_opened_tabs: int = 1,
    ):
        if browser_config is None:
            browser_config = nodriver.Config()

        browser_config.headless = headless
        browser_config.add_argument("--no-default-browser-check")
        browser_config.add_argument("--no-first-run")
        if mute_audio:
            browser_config.add_argument("--mute-audio")
        if block_images:
            browser_config.add_argument("--blink-settings=imagesEnabled=false")

        self._browser_config = browser_config
        self._browser: nodriver.Browser | None = None

        self._lock = asyncio.Lock()

        self._max_opened_tabs = max_opened_tabs
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

        await tab.maximize()
        return Page(tab)

    async def close(self):
        async with self._lock:
            for tab in self.tabs:
                await tab.close()

            if self._browser:
                self._browser.stop()

        # await self.close_if_idle()
