from .browser.context import Browser as BrowserManager
from .browser.context import BrowserManagerConfig as BrowserConfig
from .browser.context import browser, get_page
from .browser.page import Page
from .browser.tools.request_interceptor import RequestInterceptor

__all__ = ["BrowserConfig", "browser", "get_page", "BrowserManager", "Page", "RequestInterceptor"]

__version__ = "0.4.0dev1"
