import asyncio
import contextvars
from contextlib import asynccontextmanager
from functools import wraps

from .browser_manager import BrowserManager

_context = contextvars.ContextVar("browser_context")


@asynccontextmanager
async def _BrowserContextManager():
    browser = BrowserManager()
    _context.set(browser)
    yield browser
    await browser.close()


async def async_browser(func, *args, **kwargs):
    async with _BrowserContextManager():
        return await func(*args, **kwargs)


def browser():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return asyncio.run(async_browser(func, *args, **kwargs))

        return wrapper

    return decorator


async def get_page():
    browser: BrowserManager = _context.get()
    return await browser.new_page()
