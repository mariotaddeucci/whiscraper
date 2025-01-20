import asyncio
import contextvars
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import wraps

from whiscraper.browser.browser_manager import BrowserManager, BrowserManagerConfig

_context = contextvars.ContextVar("browser_context")


@asynccontextmanager
async def Browser(config: BrowserManagerConfig | None = None):
    browser = BrowserManager(config=config)
    _context.set(browser)
    yield browser
    await browser.close()


async def async_browser(config: BrowserManagerConfig | None, func: Callable, *args, **kwargs):
    async with Browser(config=config):
        return await func(*args, **kwargs)


def browser(config: BrowserManagerConfig | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                is_event_loop_running = asyncio.get_event_loop().is_running()
            except RuntimeError:
                is_event_loop_running = False

            nonlocal config
            if is_event_loop_running:
                return async_browser(config, func, *args, **kwargs)

            return asyncio.run(async_browser(config, func, *args, **kwargs))

        return wrapper

    return decorator


async def get_page():
    browser: BrowserManager = _context.get()
    return await browser.new_page()
