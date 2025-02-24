import asyncio
import fnmatch
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Callable, Tuple

import nodriver


@dataclass(frozen=True)
class InterceptedResponse:
    event: nodriver.cdp.network.ResponseReceived
    intercepted_at: datetime = field(default_factory=datetime.now, init=False)

    async def ensure_body_downloaded(self) -> None:
        seconds_from_creation = (datetime.now() - self.intercepted_at).total_seconds()
        await asyncio.sleep(max(2 - seconds_from_creation, 0))


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
        self._intercept_event = asyncio.Event()
        self._intercepted_responses: deque[InterceptedResponse] = deque()
        self._sniffers: list[Callable[[nodriver.cdp.network.ResponseReceived], bool]] = []

    @staticmethod
    def _sniffer_check(
        event: nodriver.cdp.network.ResponseReceived,
        patterns: list[str],
        filter_fn: Callable[[nodriver.cdp.network.ResponseReceived], bool] | None,
    ) -> bool:
        if not any(fnmatch.fnmatch(event.response.url.lower(), pattern) for pattern in patterns):
            return False
        if filter_fn is None:
            return True
        return filter_fn(event)

    def sniff(
        self,
        *patterns: list[str] | str,
        filter_fn: Callable[[nodriver.cdp.network.ResponseReceived], bool] | None = None,
    ):
        if len(self._sniffers) == 0:
            self._tab.add_handler(
                nodriver.cdp.network.ResponseReceived,
                self._cdp_receive_handler,
            )

        sniff_patterns = [
            p.lower() for pattern in patterns for p in (pattern if isinstance(pattern, list) else [pattern])
        ]

        self._sniffers.append(partial(self._sniffer_check, patterns=sniff_patterns, filter_fn=filter_fn))

        return self

    async def _cdp_receive_handler(self, event: nodriver.cdp.network.ResponseReceived):
        if not any(sniffer(event) for sniffer in self._sniffers):
            return

        self._intercepted_responses.append(InterceptedResponse(event=event))
        self._intercept_event.set()

    async def take(self, total: int, include_body: bool = True, timeout: float = 10):
        for _ in range(total):
            for _ in range(int(timeout + 1)):
                if not self.empty:
                    break
                await asyncio.sleep(1)
            else:
                raise TimeoutError("Timeout waiting for intercepted responses")

            intercepted_response = self._intercepted_responses.popleft()
            await intercepted_response.ensure_body_downloaded()
            event = intercepted_response.event

            resp_factory_fn = partial(
                Response,
                url=event.response.url,
                request_id=str(event.request_id),
                headers=dict(event.response.headers),
                status_code=event.response.status,
            )

            if not include_body or event.response.status == 204:
                yield resp_factory_fn(body=None)
                return

            cdp_command = nodriver.cdp.network.get_response_body(event.request_id)
            response_body: Tuple[str, bool] | None = await self._tab.send(cdp_command)

            if response_body is None:
                yield resp_factory_fn(body=None)
                return

            body_text, is_base64_encoded = response_body
            if is_base64_encoded:
                body_text = body_text.encode("utf-8").decode("base64")

            yield resp_factory_fn(body=body_text)

    async def get(self, include_body: bool = True, timeout: float = 10):
        async for vl in self.take(1, include_body=include_body, timeout=timeout):
            return vl

    async def get_all(self, include_body: bool = True, timeout: float = 10):
        while not self.empty:
            vl = await self.get(include_body=include_body, timeout=timeout)
            yield vl

    @property
    def empty(self) -> bool:
        return len(self._intercepted_responses) == 0

    def clear(self) -> None:
        self._intercepted_responses.clear()

    def reset(self) -> None:
        self.clear()
        self._sniffers.clear()

    async def wait(self):
        await self._intercept_event.wait()
        self._intercept_event.clear()
