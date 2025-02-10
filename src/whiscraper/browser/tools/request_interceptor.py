import asyncio
import fnmatch
import math
from dataclasses import dataclass
from functools import partial
from typing import Callable, Tuple

import nodriver


@dataclass(frozen=True)
class Response:
    request_id: str
    url: str
    headers: dict[str, str]
    status_code: int
    body: str | None = None


class RequestInterceptor:
    def __init__(self, tab: nodriver.Tab):
        self._tab = tab
        self._intercepted_responses = asyncio.Queue()
        self._patterns: list[str] = []
        self._filters: list[Callable[[nodriver.cdp.network.ResponseReceived], bool]] = []

    def _match(self, url: str) -> bool:
        return any(fnmatch.fnmatch(url.lower(), pattern) for pattern in self._patterns)

    def sniff(self, *patterns: list[str] | str):
        if len(self._patterns) == 0:
            self._tab.add_handler(
                nodriver.cdp.network.ResponseReceived,
                self._cdp_receive_handler,
            )

        for pattern in patterns:
            if isinstance(pattern, list):
                for p in pattern:
                    self._patterns.append(p.lower())
            else:
                self._patterns.append(pattern.lower())

        return self

    async def _cdp_receive_handler(self, event: nodriver.cdp.network.ResponseReceived):
        if not self._match(event.response.url):
            return

        if not all(fn(event) for fn in self._filters):
            return

        await self._intercepted_responses.put(event)

    async def take(self, total: int, include_body: bool = True, timeout: float = 10, body_collect_timeout: int = 5):
        for _ in range(total):
            item: nodriver.cdp.network.ResponseReceived = await asyncio.wait_for(
                self._intercepted_responses.get(), timeout
            )

            resp_factory_fn = partial(
                Response,
                url=item.response.url,
                request_id=str(item.request_id),
                headers=dict(item.response.headers),
                status_code=item.response.status,
            )

            if not include_body or item.response.status == 204:
                yield resp_factory_fn(body=None)
                return

            cdp_command = nodriver.cdp.network.get_response_body(item.request_id)

            for i in range(body_collect_timeout):
                response_body: Tuple[str, bool] | None = await self._tab.send(cdp_command)
                if response_body is not None:
                    break
                elif i < body_collect_timeout - 1:
                    await asyncio.sleep(1)
            else:
                yield resp_factory_fn(body=None)
                return

            body_text, is_base64_encoded = response_body

            if is_base64_encoded:
                body_text = body_text.encode("utf-8").decode("base64")

            yield resp_factory_fn(body=body_text)

    async def get(self, include_body: bool = True, timeout: float = 10):
        async for vl in self.take(1, include_body=include_body, timeout=timeout):
            return vl

    def filter(self, fn: Callable[[nodriver.cdp.network.ResponseReceived], bool]):
        self._filters.append(fn)
        return self

    def has_response(self):
        return not self._intercepted_responses.empty()
