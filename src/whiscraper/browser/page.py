import asyncio
import random
from functools import cached_property

import nodriver

from .tools.captcha_solver import CaptchaSolver
from .tools.request_interceptor import RequestInterceptor


class Page:
    def __init__(self, page: nodriver.Tab):
        self._page = page
        self._intercepted_responses = asyncio.Queue()

    @property
    def tab(self) -> nodriver.Tab:
        return self._page

    async def fill(self, selector: str, value: str, clear: bool = True, timeout: float = 10) -> nodriver.Element:
        obj = await self.click(selector, timeout=timeout)
        await obj.send_keys(value)
        return obj

    async def click(self, selector: str, timeout: float = 10) -> nodriver.Element:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        obj = await self.tab.wait_for(selector, timeout=timeout)
        await obj.mouse_move()
        await obj.mouse_click()
        return obj

    async def get(self, url: str, wait_page_load: bool = True):
        await self.tab.get(url)
        if wait_page_load:
            await self.tab
            await asyncio.sleep(random.uniform(0.5, 1.5))

    @cached_property
    def interceptor(self) -> RequestInterceptor:
        return RequestInterceptor(self.tab)

    @cached_property
    def captcha(self) -> CaptchaSolver:
        return CaptchaSolver(self.tab)
