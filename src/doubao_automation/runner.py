from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
import logging
import shutil
from pathlib import Path
from datetime import datetime
from tempfile import mkdtemp

from playwright.async_api import Error, Page, Playwright, async_playwright

from doubao_automation.browser import get_primary_page, open_persistent_context
from doubao_automation.config import Settings

logger = logging.getLogger(__name__)

LOGIN_WINDOW_CLOSED_MESSAGE = (
    "登录窗口在浏览器 Profile 完成保存前被关闭了。请重新执行登录，并在完成登录后保持窗口打开，直到程序检测到登录成功。"
)
LOGIN_WAIT_TIMEOUT_MESSAGE = "在等待时间内未检测到登录完成。请确认页面右上角的“登录”入口已经消失后再重试。"
SAVED_LOGIN_INVALID_MESSAGE = (
    "当前浏览器 Profile 中没有可复用的登录态：打开页面后右上角仍然显示“登录”。请重新执行登录流程。"
)
LOGIN_EXPIRED_ON_SUBMIT_MESSAGE = (
    "点击提交后页面跳转到了 from_logout=1，当前浏览器 Profile 的登录态在真正发起生成请求时已失效。请重新登录后再试。"
)


def _is_profile_lock_error(exc: Error) -> bool:
    message = str(exc)
    return "ProcessSingleton" in message or "SingletonLock" in message


def _copy_browser_profile(source_dir: Path) -> Path:
    def _copy_file_skip_missing(src: str, dst: str) -> str:
        try:
            return shutil.copy2(src, dst)
        except FileNotFoundError:
            return dst

    temp_dir = Path(mkdtemp(prefix="doubao-browser-profile-", dir="/tmp"))
    shutil.rmtree(temp_dir)
    shutil.copytree(
        source_dir,
        temp_dir,
        copy_function=_copy_file_skip_missing,
        ignore=shutil.ignore_patterns("Singleton*", "DevToolsActivePort"),
    )
    return temp_dir


def has_saved_login(settings: Settings) -> bool:
    return settings.browser_profile_dir.exists() and any(settings.browser_profile_dir.iterdir())


async def _safe_close_context(context, *, timeout_seconds: float = 5) -> None:
    try:
        await asyncio.wait_for(context.close(), timeout=timeout_seconds)
    except (Error, TimeoutError, asyncio.CancelledError) as exc:
        logger.warning("Ignoring browser context close failure during cleanup: %s", exc)


async def _safe_stop_playwright(playwright: Playwright, *, timeout_seconds: float = 5) -> None:
    try:
        await asyncio.wait_for(playwright.stop(), timeout=timeout_seconds)
    except (Error, TimeoutError, asyncio.CancelledError) as exc:
        logger.warning("Ignoring Playwright shutdown failure during cleanup: %s", exc)


async def human_pause(seconds: float = 0.8) -> None:
    await asyncio.sleep(seconds)


async def wait_for_login_completion(page: Page, timeout_ms: int) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    login_button = page.get_by_role("button", name="登录").first
    login_link = page.get_by_role("link", name="登录").first
    login_entry_seen = False

    while True:
        login_button_visible = await login_button.is_visible()
        login_link_visible = await login_link.is_visible()

        if login_button_visible or login_link_visible:
            login_entry_seen = True

        if login_entry_seen and not login_button_visible and not login_link_visible:
            logger.info("Detected logged-in state because the 登录 entry is no longer visible.")
            return

        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(LOGIN_WAIT_TIMEOUT_MESSAGE)

        await page.wait_for_timeout(1000)


async def has_login_entry(page: Page) -> bool:
    login_button = page.get_by_role("button", name="登录").first
    login_link = page.get_by_role("link", name="登录").first
    return await login_button.is_visible() or await login_link.is_visible()


async def ensure_login(settings: Settings) -> None:
    logger.info("Opening login session for %s", settings.target_url)
    logger.info(
        "Complete the login in the browser window within %s seconds. Browser profile dir: %s",
        settings.login_wait_seconds,
        settings.browser_profile_dir,
    )

    async with async_playwright() as playwright:
        context = await open_persistent_context(playwright, settings, headless=False)
        page = await get_primary_page(context)
        login_saved = False
        try:
            await page.goto(settings.target_url, timeout=settings.timeout_ms)
            await wait_for_login_completion(page, timeout_ms=settings.login_wait_seconds * 1000)
            login_saved = True
            logger.info("Login state is now available in browser profile %s", settings.browser_profile_dir)
            logger.info("Leave the browser open and close it manually when finished.")
            await context.wait_for_event("close")
            logger.info("Login browser window closed by user.")
        except Error as exc:
            if "Target page, context or browser has been closed" in str(exc):
                if login_saved:
                    logger.info("Login browser window closed after auth state was saved.")
                    return
                else:
                    raise RuntimeError(LOGIN_WINDOW_CLOSED_MESSAGE) from exc
            raise
        finally:
            if context is not None:
                await _safe_close_context(context)

    logger.info("Login session closed. Browser profile can be reused for later runs.")


async def open_new_chat(page: Page, timeout_ms: int) -> None:
    new_chat_entry = page.locator("nav").get_by_text("新对话", exact=True).first
    await new_chat_entry.wait_for(state="visible", timeout=timeout_ms)
    await new_chat_entry.click(timeout=timeout_ms)
    logger.info("Clicked entry: 新对话")


async def open_ai_creation(page: Page, timeout_ms: int) -> None:
    ai_creation_link = page.get_by_role("link", name="AI 创作").first
    await ai_creation_link.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    await ai_creation_link.click(timeout=timeout_ms)
    await page.wait_for_url("**/chat/create-image**", timeout=timeout_ms)
    await human_pause(1.0)
    logger.info("Clicked entry: AI 创作")


async def upload_reference_image(page: Page, image_path: Path, timeout_ms: int) -> None:
    if not image_path.exists():
        raise RuntimeError(
            f"Reference image not found: {image_path}. Set AUTOMATION_REFERENCE_IMAGE_PATH to a valid file."
        )

    reference_button = page.get_by_role("button", name="参考图").first
    await reference_button.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    async with page.expect_file_chooser() as file_chooser_info:
        await reference_button.click(timeout=timeout_ms)

    file_chooser = await file_chooser_info.value
    await file_chooser.set_files(str(image_path))
    await page.get_by_role("textbox").first.wait_for(state="visible", timeout=timeout_ms)
    await human_pause(1.2)
    logger.info("Uploaded reference image: %s", image_path)


async def ensure_image_generation_mode(page: Page, timeout_ms: int) -> None:
    await ensure_creation_mode(page, mode="图像", timeout_ms=timeout_ms)


async def ensure_creation_mode(page: Page, *, mode: str, timeout_ms: int) -> None:
    mode_button = page.get_by_role("button", name="图像 视频").first
    await mode_button.wait_for(state="visible", timeout=timeout_ms)
    active_mode = await mode_button.evaluate(
        """button => {
            const activeOption = [...button.querySelectorAll('div')]
                .find(node => node.className.includes('bg-s-color-brand-primary-transparent-1'));
            return activeOption?.textContent?.trim() || "";
        }"""
    )
    if active_mode == mode:
        logger.info("%s generation mode is already selected.", mode)
        return

    await mode_button.locator("div", has_text=mode).first.click(timeout=timeout_ms)
    await human_pause(0.8)
    logger.info("Switched generation mode to %s.", mode)


async def enter_video_generation_from_chat(page: Page, timeout_ms: int) -> None:
    candidate_locators = [
        page.get_by_role("button", name="视频生成").first,
        page.get_by_role("button", name="生成视频").first,
        page.get_by_text("视频生成", exact=True).first,
        page.get_by_text("生成视频", exact=True).first,
    ]
    for locator in candidate_locators:
        try:
            await locator.wait_for(state="visible", timeout=1500)
            await human_pause()
            await locator.click(timeout=timeout_ms)
            await human_pause(1.0)
            logger.info("Entered video generation from the existing image chat.")
            return
        except Error:
            continue
        except TimeoutError:
            continue

    logger.info("No dedicated video entry found in the image chat. Falling back to the mode switcher.")
    await ensure_creation_mode(page, mode="视频", timeout_ms=timeout_ms)


async def select_image_ratio(page: Page, ratio: str, timeout_ms: int) -> None:
    await select_creation_ratio(page, ratio=ratio, timeout_ms=timeout_ms)


async def select_creation_ratio(page: Page, *, ratio: str, timeout_ms: int) -> None:
    ratio_button = page.get_by_role("button", name="比例").last
    await ratio_button.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    await ratio_button.click(timeout=timeout_ms)
    ratio_menu = page.get_by_role("menu", name="比例")
    await ratio_menu.wait_for(state="visible", timeout=timeout_ms)
    await human_pause(0.6)
    ratio_option = ratio_menu.get_by_role("menuitem").filter(has_text=ratio).first
    await ratio_option.wait_for(state="visible", timeout=timeout_ms)
    await ratio_option.click(timeout=timeout_ms)
    await ratio_menu.wait_for(state="hidden", timeout=timeout_ms)
    await human_pause(0.8)
    logger.info("Selected image ratio: %s", ratio)


async def fill_image_prompt(page: Page, prompt: str, timeout_ms: int) -> None:
    prompt_input = page.get_by_test_id("chat_input_input").first
    await prompt_input.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    await prompt_input.click(timeout=timeout_ms)
    await human_pause(0.4)
    await prompt_input.fill(prompt, timeout=timeout_ms)
    await human_pause(0.6)
    logger.info("Filled image prompt.")


async def fill_video_prompt(page: Page, prompt: str, timeout_ms: int) -> None:
    prompt_input = page.get_by_test_id("chat_input_input").first
    await prompt_input.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    await prompt_input.click(timeout=timeout_ms)
    await human_pause(0.4)
    await prompt_input.fill(prompt, timeout=timeout_ms)
    await human_pause(0.6)
    logger.info("Filled video prompt.")


async def wait_for_generation_chat(page: Page, timeout_ms: int) -> str:
    await page.wait_for_function(
        """() => {
            const path = window.location.pathname;
            return path.startsWith('/chat/') && path !== '/chat/create-image';
        }""",
        timeout=timeout_ms,
    )
    if "/chat/create-image" in page.url:
        raise RuntimeError("Prompt submission did not navigate to a generated chat session.")
    logger.info("Generation chat opened: %s", page.url)
    return page.url


async def capture_current_chat_url(page: Page) -> str:
    current_url = await page.evaluate("() => window.location.href")
    logger.info("Captured current browser URL before cleanup: %s", current_url)
    return current_url


async def list_generation_image_urls(page: Page) -> list[str]:
    return await page.evaluate(
        """() => {
            const messageImages = [...document.querySelectorAll(
                '[data-testid="message_image_content"][data-finished="true"] img'
            )]
                .map(img => img.getAttribute('src') || '')
                .filter(src => src.startsWith('http'));
            return [...new Set(messageImages)];
        }"""
    )


async def submit_image_prompt(page: Page, timeout_ms: int) -> None:
    send_button = page.get_by_test_id("chat_input_send_button")
    await send_button.wait_for(state="visible", timeout=timeout_ms)
    await human_pause()
    await send_button.click(timeout=timeout_ms)
    await human_pause(1.0)
    if "from_logout=1" in page.url:
        raise RuntimeError(LOGIN_EXPIRED_ON_SUBMIT_MESSAGE)
    logger.info("Submitted image prompt.")


async def submit_video_generation(
    settings: Settings,
    *,
    reference_image_path: Path,
    use_image_chat: bool = True,
    image_chat_url: str | None = None,
    headless: bool | None = None,
) -> str:
    if not has_saved_login(settings):
        raise RuntimeError("No reusable browser profile found. Run the login flow first.")

    effective_headless = settings.headless if headless is None else headless
    entry_url = image_chat_url if use_image_chat else settings.target_url
    if use_image_chat and not image_chat_url:
        raise RuntimeError("当前任务还没有节点2豆包地址，请先完成一次图片生成，或关闭“基于节点2对话框生成视频”。")

    logger.info(
        "Opening %s for video submission with headless=%s (use_image_chat=%s)",
        entry_url,
        effective_headless,
        use_image_chat,
    )

    playwright: Playwright | None = None
    context = None
    temp_profile_dir: Path | None = None
    try:
        playwright = await async_playwright().start()
        try:
            context = await open_persistent_context(playwright, settings, headless=effective_headless)
        except Error as exc:
            if not _is_profile_lock_error(exc):
                raise
            logger.info(
                "Browser profile %s is locked by another Chrome instance. Using a temporary copy for this run.",
                settings.browser_profile_dir,
            )
            temp_profile_dir = _copy_browser_profile(settings.browser_profile_dir)
            temp_settings = replace(settings, browser_profile_dir=temp_profile_dir)
            context = await open_persistent_context(playwright, temp_settings, headless=effective_headless)
        page = await get_primary_page(context)
        await page.goto(entry_url, timeout=settings.timeout_ms)
        await page.wait_for_load_state("domcontentloaded")
        await human_pause(1.5)
        if await has_login_entry(page):
            raise RuntimeError(SAVED_LOGIN_INVALID_MESSAGE)
        if use_image_chat:
            await enter_video_generation_from_chat(page, timeout_ms=settings.timeout_ms)
        else:
            await open_ai_creation(page, timeout_ms=settings.timeout_ms)
            await ensure_creation_mode(page, mode="视频", timeout_ms=settings.timeout_ms)
        await upload_reference_image(page, reference_image_path, timeout_ms=settings.timeout_ms)
        await fill_video_prompt(page, settings.video_prompt, timeout_ms=settings.timeout_ms)
        await select_creation_ratio(page, ratio=settings.image_ratio, timeout_ms=settings.timeout_ms)
        await submit_image_prompt(page, timeout_ms=settings.timeout_ms)
        if not use_image_chat:
            await wait_for_generation_chat(page, timeout_ms=settings.timeout_ms)
        await human_pause(1.5)
        return await capture_current_chat_url(page)
    finally:
        if context is not None:
            await _safe_close_context(context)
        if playwright is not None:
            await _safe_stop_playwright(playwright)
        if temp_profile_dir is not None and temp_profile_dir.exists():
            shutil.rmtree(temp_profile_dir, ignore_errors=True)


async def wait_for_generated_images(
    page: Page,
    existing_urls: set[str],
    timeout_seconds: int,
) -> list[str]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    first_seen_at: float | None = None
    latest_count = 0

    while True:
        current_urls = await list_generation_image_urls(page)
        new_urls = [url for url in current_urls if url not in existing_urls]
        if new_urls:
            current_count = len(new_urls)
            if current_count != latest_count:
                latest_count = current_count
                first_seen_at = asyncio.get_running_loop().time()
            elif first_seen_at is not None and asyncio.get_running_loop().time() - first_seen_at >= 4.0:
                return new_urls

        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"No generated image appeared within {timeout_seconds} seconds."
            )

        await human_pause(2.0)


async def save_generated_images(
    page: Page,
    image_urls: list[str],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    saved_paths: list[Path] = []

    for index, image_url in enumerate(image_urls, start=1):
        payload = await page.evaluate(
            """async (url) => {
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`Failed to fetch generated image: ${response.status}`);
                }
                const contentType = response.headers.get("content-type") || "image/jpeg";
                const bytes = new Uint8Array(await response.arrayBuffer());
                let binary = "";
                const chunkSize = 0x8000;
                for (let i = 0; i < bytes.length; i += chunkSize) {
                    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
                }
                return {
                    contentType,
                    base64: btoa(binary),
                };
            }""",
            image_url,
        )
        extension = ".jpg" if "jpeg" in payload["contentType"] else ".png"
        output_path = output_dir / f"generated-{timestamp}-{index}{extension}"
        output_path.write_bytes(base64.b64decode(payload["base64"]))
        saved_paths.append(output_path)

    logger.info("Saved %s generated image(s) to %s", len(saved_paths), output_dir)
    return saved_paths


async def run_once(
    settings: Settings, *, headless: bool | None = None
) -> dict[str, list[Path] | str]:
    if settings.reference_image_path is None:
        raise RuntimeError("No reference image selected. Choose a reference image before running image generation.")
    if not has_saved_login(settings):
        raise RuntimeError(
            "No reusable browser profile found. Run the login flow first."
        )

    effective_headless = settings.headless if headless is None else headless

    logger.info("Opening %s with headless=%s", settings.target_url, effective_headless)

    playwright: Playwright | None = None
    context = None
    temp_profile_dir: Path | None = None
    saved_paths: list[Path] = []
    generation_chat_url = ""
    try:
        playwright = await async_playwright().start()
        try:
            context = await open_persistent_context(playwright, settings, headless=effective_headless)
        except Error as exc:
            if not _is_profile_lock_error(exc):
                raise
            logger.info(
                "Browser profile %s is locked by another Chrome instance. "
                "Using a temporary copy for this run.",
                settings.browser_profile_dir,
            )
            temp_profile_dir = _copy_browser_profile(settings.browser_profile_dir)
            temp_settings = replace(settings, browser_profile_dir=temp_profile_dir)
            context = await open_persistent_context(playwright, temp_settings, headless=effective_headless)
        page = await get_primary_page(context)
        await page.goto(settings.target_url, timeout=settings.timeout_ms)
        await page.wait_for_load_state("domcontentloaded")
        await human_pause(1.5)
        if await has_login_entry(page):
            raise RuntimeError(SAVED_LOGIN_INVALID_MESSAGE)
        title = await page.title()
        logger.info("Page title: %s", title)
        await open_ai_creation(page, timeout_ms=settings.timeout_ms)
        await ensure_image_generation_mode(page, timeout_ms=settings.timeout_ms)
        await upload_reference_image(
            page,
            settings.reference_image_path,
            timeout_ms=settings.timeout_ms,
        )
        await fill_image_prompt(
            page,
            settings.image_prompt,
            timeout_ms=settings.timeout_ms,
        )
        await select_image_ratio(
            page,
            settings.image_ratio,
            timeout_ms=settings.timeout_ms,
        )
        await submit_image_prompt(page, timeout_ms=settings.timeout_ms)
        await wait_for_generation_chat(page, timeout_ms=settings.timeout_ms)
        existing_image_urls = set(await list_generation_image_urls(page))
        generated_image_urls = await wait_for_generated_images(
            page,
            existing_urls=existing_image_urls,
            timeout_seconds=settings.image_generation_timeout_seconds,
        )
        saved_paths = await save_generated_images(
            page,
            generated_image_urls,
            settings.generated_image_dir,
        )
        generation_chat_url = await capture_current_chat_url(page)
        logger.info("Generated image files: %s", ", ".join(str(path) for path in saved_paths))
    finally:
        if context is not None:
            await _safe_close_context(context)
        if playwright is not None:
            await _safe_stop_playwright(playwright)
        if temp_profile_dir is not None and temp_profile_dir.exists():
            shutil.rmtree(temp_profile_dir, ignore_errors=True)
    return {
        "saved_paths": saved_paths,
        "chat_url": generation_chat_url,
    }
