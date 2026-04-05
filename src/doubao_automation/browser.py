from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Page, Playwright

from doubao_automation.config import Settings


async def open_persistent_context(
    playwright: Playwright,
    settings: Settings,
    *,
    headless: bool,
) -> BrowserContext:
    settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=str(settings.browser_profile_dir),
        channel="chrome",
        headless=headless,
        viewport={"width": 1440, "height": 960},
    )


async def open_browser_context(
    playwright: Playwright,
    settings: Settings,
    *,
    headless: bool,
) -> tuple[Browser, BrowserContext]:
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        storage_state=str(settings.auth_state_path),
        viewport={"width": 1440, "height": 960},
    )
    return browser, context


async def open_login_context(
    playwright: Playwright,
    *,
    headless: bool,
) -> tuple[Browser, BrowserContext]:
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        viewport={"width": 1440, "height": 960},
    )
    return browser, context


async def get_primary_page(context: BrowserContext) -> Page:
    if context.pages:
        return context.pages[0]
    return await context.new_page()
