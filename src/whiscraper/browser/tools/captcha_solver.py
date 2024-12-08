import asyncio

import nodriver


class CaptchaSolver:
    def __init__(self, tab: nodriver.Tab):
        self._tab = tab
        self._intercepted_responses = asyncio.Queue()
        self._patterns: list[str] = []

    async def bypass_recaptcha(self):
        await self._tab
        iframe = await self._tab.select('iframe[title="reCAPTCHA"]')
        checkbox = await iframe.query_selector("div.rc-inline-block")
        if not isinstance(checkbox, nodriver.Element):
            raise RuntimeError("Checkbox not found")

        await checkbox.mouse_move()
        await checkbox.mouse_click()

    async def bypass_cloudflare(self):
        await self._tab
        await self._tab.verify_cf()
