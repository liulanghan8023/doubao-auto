from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


@dataclass(slots=True)
class Settings:
    target_url: str
    headless: bool
    timeout_ms: int
    interval_seconds: int
    screenshot_path: Path
    reference_image_path: Path | None
    image_ratio: str
    image_prompt: str
    video_prompt: str
    generated_image_dir: Path
    image_generation_timeout_seconds: int
    browser_profile_dir: Path
    auth_state_path: Path
    login_wait_seconds: int
    log_level: str


def load_settings() -> Settings:
    load_dotenv()

    screenshot_path = Path(
        os.getenv("AUTOMATION_SCREENSHOT_PATH", "runtime/example.png")
    ).expanduser()
    raw_reference_image_path = os.getenv("AUTOMATION_REFERENCE_IMAGE_PATH", "").strip()
    reference_image_path = Path(raw_reference_image_path).expanduser() if raw_reference_image_path else None

    return Settings(
        target_url=os.getenv("AUTOMATION_TARGET_URL", "https://example.com"),
        headless=_get_bool("AUTOMATION_HEADLESS", default=True),
        timeout_ms=_get_int("AUTOMATION_TIMEOUT_MS", default=30_000),
        interval_seconds=_get_int("AUTOMATION_INTERVAL_SECONDS", default=300),
        screenshot_path=screenshot_path,
        reference_image_path=reference_image_path,
        image_ratio=os.getenv("AUTOMATION_IMAGE_RATIO", "9:16"),
        image_prompt=os.getenv(
            "AUTOMATION_IMAGE_PROMPT",
            (
                "画面中心一只戴着精美美甲和手表的手提着透明大包装袋，保持手部高度绝对静止，"
                "严禁任何往上提或移动的动作。袋子装满[莲藕莲子米菱角米]，正以极其缓慢、近乎停滞的速度"
                "进行平稳自转。旋转速度设定为大约每 30 秒才转动完整一圈（极慢速匀速旋转），这种速度"
                "旨在让观众看清每一颗。袋子正面贴有“荷塘三宝”的标签。背景是整齐的仓库货架，灯光随"
                "着袋子缓慢的转动，在塑料包装表面流淌出极其细腻、缓慢变换的反光。"
            ),
        ),
        video_prompt=os.getenv(
            "AUTOMATION_VIDEO_PROMPT",
            (
                "画面中心一只戴着精美美甲和手表的手提着透明大包装袋，保持手部高度绝对静止，"
                "严禁任何往上提或移动的动作。袋子装满[莲藕莲子米菱角米]，正以极其缓慢、近乎停滞的速度"
                "进行平稳自转。旋转速度设定为大约每 30 秒才转动完整一圈（极慢速匀速旋转），这种速度"
                "旨在让观众看清每一颗。袋子正面贴有“荷塘三宝”的标签。背景是整齐的仓库货架，灯光随着"
                "袋子缓慢的转动，在塑料包装表面流淌出极其细腻、缓慢变换的反光。"
            ),
        ),
        generated_image_dir=Path(
            os.getenv("AUTOMATION_GENERATED_IMAGE_DIR", "runtime/generated-images")
        ).expanduser(),
        image_generation_timeout_seconds=_get_int(
            "AUTOMATION_IMAGE_GENERATION_TIMEOUT_SECONDS",
            default=600,
        ),
        browser_profile_dir=Path(
            os.getenv("AUTOMATION_BROWSER_PROFILE_DIR", "runtime/browser-profile")
        ).expanduser(),
        auth_state_path=Path(
            os.getenv("AUTOMATION_AUTH_STATE_PATH", "runtime/auth-state.json")
        ).expanduser(),
        login_wait_seconds=_get_int("AUTOMATION_LOGIN_WAIT_SECONDS", default=180),
        log_level=os.getenv("AUTOMATION_LOG_LEVEL", "INFO").upper(),
    )
