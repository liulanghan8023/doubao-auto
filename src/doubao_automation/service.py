from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Any, Awaitable

from doubao_automation.config import Settings
from doubao_automation.runner import ensure_login, has_saved_login, run_once, submit_video_generation
from doubao_automation.tasks import PromptTemplateRecord, TaskRecord, TaskStore

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class StatusSnapshot:
    target_url: str
    login_saved: bool
    active_job: str | None
    last_error: str | None
    last_event: str
    last_run_at: str | None
    task_defaults: dict[str, str]
    recent_outputs: list[str]
    tasks: list[dict[str, Any]]
    templates: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._project_root = Path(__file__).resolve().parents[2]
        self._task_store = TaskStore(self._project_root / "runtime" / "app.db")
        self._lock = asyncio.Lock()
        self._manual_task: asyncio.Task[None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._worker_stop_event = asyncio.Event()
        self._active_job: str | None = None
        self._last_error: str | None = None
        self._last_run_at: str | None = None
        self._last_event = _utc_now()

    def snapshot(self) -> StatusSnapshot:
        return StatusSnapshot(
            target_url=self.settings.target_url,
            login_saved=has_saved_login(self.settings),
            active_job=self._active_job,
            last_error=self._last_error,
            last_event=self._last_event,
            last_run_at=self._last_run_at,
            task_defaults={
                "reference_image_path": str(self.settings.reference_image_path) if self.settings.reference_image_path else "",
                "image_prompt": self.settings.image_prompt,
                "video_prompt": self.settings.video_prompt,
            },
            recent_outputs=self.list_recent_outputs(),
            tasks=[task.to_dict() for task in self._task_store.list_tasks()],
            templates=[template.to_dict() for template in self._task_store.list_templates()],
        )

    @property
    def worker_running(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    def schedule_login(self) -> None:
        self._ensure_manual_action_allowed()
        self._manual_task = asyncio.create_task(self._run_login_job())
        self._manual_task.add_done_callback(self._clear_manual_task)

    def schedule_once(
        self,
        *,
        task_id: str | None = None,
        image_prompt: str | None = None,
        reference_image_path: Path | None = None,
    ) -> None:
        self._ensure_manual_action_allowed()
        if not has_saved_login(self.settings):
            raise RuntimeError("No saved login found. Run the login flow first.")
        task = self.get_task(task_id) if task_id else None
        resolved_reference_image_path = reference_image_path
        if resolved_reference_image_path is None and task and task.reference_image_path:
            resolved_reference_image_path = self._project_root / task.reference_image_path
        if resolved_reference_image_path is None:
            resolved_reference_image_path = self.settings.reference_image_path
        run_settings = replace(
            self.settings,
            image_prompt=image_prompt or (task.image_prompt if task else self.settings.image_prompt),
            reference_image_path=resolved_reference_image_path,
        )
        self._manual_task = asyncio.create_task(self._run_once_job(run_settings, task_id=task_id))
        self._manual_task.add_done_callback(self._clear_manual_task)

    def create_task(
        self,
        *,
        name: str,
        image_prompt: str,
        video_prompt: str,
        reference_image_path: Path | None,
        template_id: str | None = None,
        video_reference_image_path: str | None = None,
        video_use_image_chat: bool = True,
    ) -> TaskRecord:
        if template_id:
            self.get_template(template_id)
        return self._task_store.create_task(
            name=name,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
            reference_image_path=self._to_runtime_relative(reference_image_path) if reference_image_path else "",
            template_id=template_id,
            video_reference_image_path=video_reference_image_path,
            video_use_image_chat=video_use_image_chat,
        )

    def update_task(
        self,
        task_id: str,
        *,
        name: str,
        image_prompt: str,
        video_prompt: str,
        reference_image_path: Path | None = None,
        template_id: str | None = None,
        video_reference_image_path: str | None = None,
        video_use_image_chat: bool = True,
    ) -> TaskRecord:
        existing = self.get_task(task_id)
        resolved_reference = (
            self._to_runtime_relative(reference_image_path)
            if reference_image_path is not None
            else existing.reference_image_path
        )
        if template_id:
            self.get_template(template_id)
        return self._task_store.update_task(
            task_id,
            name=name,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
            reference_image_path=resolved_reference,
            template_id=template_id,
            video_reference_image_path=video_reference_image_path,
            video_use_image_chat=video_use_image_chat,
        )

    def list_tasks(self) -> list[TaskRecord]:
        return self._task_store.list_tasks()

    def list_templates(self) -> list[PromptTemplateRecord]:
        return self._task_store.list_templates()

    def get_template(self, template_id: str | None) -> PromptTemplateRecord:
        if template_id is None:
            raise RuntimeError("Template id is required.")
        try:
            return self._task_store.get_template(template_id)
        except KeyError as exc:
            raise RuntimeError(f"Template not found: {template_id}") from exc

    def create_template(self, *, name: str, image_prompt: str, video_prompt: str) -> PromptTemplateRecord:
        normalized_name = name.strip()
        if self._task_store.template_name_exists(normalized_name):
            raise RuntimeError(f"模板名称已存在：{normalized_name}")
        return self._task_store.create_template(
            name=normalized_name,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
        )

    def update_template(
        self,
        template_id: str,
        *,
        name: str,
        image_prompt: str,
        video_prompt: str,
    ) -> PromptTemplateRecord:
        normalized_name = name.strip()
        try:
            if self._task_store.template_name_exists(normalized_name, excluding_template_id=template_id):
                raise RuntimeError(f"模板名称已存在：{normalized_name}")
            template = self._task_store.update_template(
                template_id,
                name=normalized_name,
                image_prompt=image_prompt,
                video_prompt=video_prompt,
            )
        except KeyError as exc:
            raise RuntimeError(f"Template not found: {template_id}") from exc
        return template

    def delete_template(self, template_id: str) -> None:
        try:
            self._task_store.get_template(template_id)
        except KeyError as exc:
            raise RuntimeError(f"Template not found: {template_id}") from exc
        self._task_store.delete_template(template_id)

    def delete_task(self, task_id: str) -> None:
        self._ensure_manual_action_allowed()
        task = self.get_task(task_id)
        owned_paths = self._collect_task_owned_paths(task)
        self._task_store.delete_task(task_id)
        for path in owned_paths:
            self._delete_runtime_file(path, task_id=task_id)

    def get_task(self, task_id: str | None) -> TaskRecord:
        if task_id is None:
            raise RuntimeError("Task id is required.")
        try:
            return self._task_store.get_task(task_id)
        except KeyError as exc:
            raise RuntimeError(f"Task not found: {task_id}") from exc

    def start_worker(self) -> None:
        if self.worker_running:
            raise RuntimeError("Worker is already running.")
        if not has_saved_login(self.settings):
            raise RuntimeError("No saved login found. Run the login flow first.")

        self._worker_stop_event = asyncio.Event()
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._mark_event()

    def schedule_video_submission(self, *, task_id: str) -> None:
        self._ensure_manual_action_allowed()
        if not has_saved_login(self.settings):
            raise RuntimeError("No saved login found. Run the login flow first.")
        task = self.get_task(task_id)
        if not task.last_outputs:
            raise RuntimeError("No image output found for this task. Generate an image first.")
        reference_image_path = self._project_root / task.last_outputs[0]
        self._manual_task = asyncio.create_task(
            self._run_video_job(
                task_id=task_id,
                reference_image_path=reference_image_path,
                video_prompt=task.video_prompt,
                video_use_image_chat=task.video_use_image_chat,
                image_chat_url=task.image_chat_url,
            )
        )
        self._manual_task.add_done_callback(self._clear_manual_task)

    async def run_once_now(
        self,
        *,
        task_id: str,
        image_prompt: str | None = None,
        reference_image_path: Path | None = None,
    ) -> TaskRecord:
        self._ensure_manual_action_allowed()
        if not has_saved_login(self.settings):
            raise RuntimeError("No saved login found. Run the login flow first.")
        task = self.get_task(task_id)
        resolved_reference_image_path = reference_image_path
        if resolved_reference_image_path is None and task.reference_image_path:
            resolved_reference_image_path = self._project_root / task.reference_image_path
        run_settings = replace(
            self.settings,
            image_prompt=image_prompt or task.image_prompt,
            reference_image_path=resolved_reference_image_path,
        )
        await self._run_once_job(run_settings, task_id=task_id)
        return self.get_task(task_id)

    async def submit_video_now(self, *, task_id: str) -> TaskRecord:
        self._ensure_manual_action_allowed()
        if not has_saved_login(self.settings):
            raise RuntimeError("No saved login found. Run the login flow first.")
        task = self.get_task(task_id)
        if not task.last_outputs:
            raise RuntimeError("No image output found for this task. Generate an image first.")
        reference_output = task.video_reference_image_path if task.video_reference_image_path in (task.last_outputs or []) else ""
        await self._run_video_job(
            task_id=task_id,
            reference_image_path=self._project_root / (reference_output or task.last_outputs[0]),
            video_prompt=task.video_prompt,
            video_use_image_chat=task.video_use_image_chat,
            image_chat_url=task.image_chat_url,
        )
        return self.get_task(task_id)

    async def stop_worker(self) -> None:
        if not self.worker_running or self._worker_task is None:
            return

        self._worker_stop_event.set()
        await self._worker_task
        self._mark_event()

    def _ensure_manual_action_allowed(self) -> None:
        if self._manual_task is not None and not self._manual_task.done():
            raise RuntimeError("Another automation action is already running.")
        if self.worker_running:
            raise RuntimeError("Worker is running. Stop it before starting a manual action.")

    async def _run_login_job(self) -> None:
        await self._run_serialized_job("login", ensure_login(self.settings))

    async def _run_once_job(self, settings: Settings, *, task_id: str | None) -> None:
        result = await self._run_serialized_job("run-once", run_once(settings, headless=False))
        if task_id is None:
            return
        saved_paths = (result or {}).get("saved_paths", [])
        chat_url = (result or {}).get("chat_url")
        if settings.reference_image_path is None:
            raise RuntimeError("请先在界面上选择参考图片。")
        saved_output_paths = [self._to_runtime_relative(path) for path in saved_paths]
        self._task_store.update_task(
            task_id,
            image_prompt=settings.image_prompt,
            reference_image_path=self._to_runtime_relative(settings.reference_image_path),
            image_chat_url=chat_url,
            video_reference_image_path=saved_output_paths[0] if saved_output_paths else None,
        )
        self._task_store.replace_outputs(
            task_id,
            "image",
            saved_output_paths,
        )

    async def _run_video_job(
        self,
        *,
        task_id: str,
        reference_image_path: Path,
        video_prompt: str,
        video_use_image_chat: bool,
        image_chat_url: str | None,
    ) -> None:
        chat_url = await self._run_serialized_job(
            "run-video",
            submit_video_generation(
                replace(self.settings, video_prompt=video_prompt),
                reference_image_path=reference_image_path,
                use_image_chat=video_use_image_chat,
                image_chat_url=image_chat_url,
                headless=False,
            ),
        )
        if not chat_url:
            return
        self._task_store.update_task(
            task_id,
            video_status="submitted",
            video_chat_url=chat_url,
            video_reference_image_path=self._to_runtime_relative(reference_image_path),
        )

    async def _run_serialized_job(self, job_name: str, operation: Awaitable[Any]) -> Any:
        async with self._lock:
            self._active_job = job_name
            self._last_error = None
            self._mark_event()
            try:
                result = await operation
                if job_name != "login":
                    self._last_run_at = _utc_now()
                return result
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Automation job failed: %s", job_name)
                return None
            finally:
                self._active_job = None
                self._mark_event()

    async def _worker_loop(self) -> None:
        self._active_job = "worker"
        self._mark_event()
        try:
            while not self._worker_stop_event.is_set():
                await self._run_serialized_job("worker-cycle", run_once(self.settings))
                try:
                    await asyncio.wait_for(
                        self._worker_stop_event.wait(),
                        timeout=self.settings.interval_seconds,
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            self._active_job = None
            self._mark_event()

    def _mark_event(self) -> None:
        self._last_event = _utc_now()

    def _clear_manual_task(self, _task: asyncio.Task[None]) -> None:
        self._manual_task = None

    def read_logs(self, limit: int = 200) -> list[str]:
        log_path = Path(__file__).resolve().parents[2] / "runtime" / "app.log"
        if not log_path.exists():
            return []

        lines = log_path.read_text(encoding="utf-8").splitlines()
        return lines[-limit:]

    def list_recent_outputs(self, limit: int = 8) -> list[str]:
        output_dir = (self._project_root / self.settings.generated_image_dir).resolve()
        if not output_dir.exists():
            return []
        files = sorted(
            (path for path in output_dir.iterdir() if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return [
            str(path.resolve().relative_to(self._project_root)).replace("\\", "/")
            for path in files[:limit]
        ]

    def _to_runtime_relative(self, path: Path) -> str:
        resolved = path.resolve()
        return str(resolved.relative_to(self._project_root)).replace("\\", "/")

    def _collect_task_owned_paths(self, task: TaskRecord) -> list[str]:
        seen: set[str] = set()
        paths: list[str] = []
        for candidate in [
            task.reference_image_path,
            task.video_reference_image_path,
            *(task.last_outputs or []),
        ]:
            if candidate and candidate not in seen:
                seen.add(candidate)
                paths.append(candidate)
        return paths

    def _delete_runtime_file(self, relative_path: str, *, task_id: str) -> None:
        if self._task_store.path_reference_count(relative_path, excluding_task_id=task_id) > 0:
            return
        candidate = (self._project_root / relative_path).resolve()
        runtime_root = (self._project_root / "runtime").resolve()
        try:
            candidate.relative_to(runtime_root)
        except ValueError:
            return
        if not candidate.exists():
            return
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
