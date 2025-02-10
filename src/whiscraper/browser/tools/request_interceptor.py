import asyncio
import fnmatch
from collections import deque
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
        self._lock = asyncio.Lock()
        self._debounce_task: asyncio.Task | None = None
        self._debounce_event = asyncio.Event()
        self._intercepted_responses: deque[nodriver.cdp.network.ResponseReceived] = deque()
        self._patterns: list[str] = []
        self._filters: list[Callable[[nodriver.cdp.network.ResponseReceived], bool]] = []

    async def _debounce_event_trigger(self):
        await asyncio.sleep(2)
        async with self._lock:
            self._debounce_event.set()

    async def _add_intercepted_response(self, response: nodriver.cdp.network.ResponseReceived):
        async with self._lock:
            self._intercepted_responses.append(response)
            if self._debounce_task:
                self._debounce_task.cancel()
            self._debounce_event.clear()
            self.task = asyncio.create_task(self._debounce_event_trigger())

    async def _pop_intercepted_response(self, timeout: float = 10) -> nodriver.cdp.network.ResponseReceived:
        async with asyncio.timeout(timeout):
            await self._debounce_event.wait()
        event = self._intercepted_responses.popleft()
        if self.empty:
            self._debounce_event.clear()
        return event

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

        await self._add_intercepted_response(event)

    async def take(self, total: int, include_body: bool = True, timeout: float = 10, body_collect_timeout: int = 5):
        for _ in range(total):
            item = await self._pop_intercepted_response(timeout=timeout)

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
                if response_body is not None and response_body[0].strip():
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

    async def get(self, include_body: bool = True, timeout: float = 10, body_collect_timeout: int = 5):
        async for vl in self.take(
            1, include_body=include_body, timeout=timeout, body_collect_timeout=body_collect_timeout
        ):
            return vl

    def filter(self, fn: Callable[[nodriver.cdp.network.ResponseReceived], bool]):
        self._filters.append(fn)
        return self

    @property
    def empty(self) -> bool:
        return len(self._intercepted_responses) > 0
