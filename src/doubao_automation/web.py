from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from doubao_automation.config import Settings, load_settings
from doubao_automation.logging import configure_logging, get_app_log_path
from doubao_automation.service import AutomationService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"
WEB_DIST_DIR = WEB_DIR / "dist"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
UPLOADS_DIR = RUNTIME_DIR / "uploads"


def _parse_form_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def create_app(settings: Settings | None = None) -> FastAPI:
    loaded_settings = settings or load_settings()
    configure_logging(loaded_settings.log_level)

    app = FastAPI(title="Doubao Automation")
    service = AutomationService(loaded_settings)
    app.state.service = service

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    assets_dir = WEB_DIST_DIR / "assets"
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    app.mount("/artifacts", StaticFiles(directory=RUNTIME_DIR), name="artifacts")

    async def read_text_payload(request: Request) -> dict[str, str]:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            raw_payload = await request.json()
            if not isinstance(raw_payload, dict):
                return {}
            return {str(key): str(value) for key, value in raw_payload.items() if value is not None}
        form_payload = await request.form()
        return {str(key): str(value) for key, value in form_payload.items() if value is not None}

    @app.get("/api/status")
    async def get_status() -> dict[str, object]:
        return service.snapshot().to_dict()

    @app.get("/api/tasks")
    async def list_tasks() -> dict[str, object]:
        return {"tasks": [task.to_dict() for task in service.list_tasks()]}

    @app.get("/api/templates")
    async def list_templates() -> dict[str, object]:
        return {"templates": [template.to_dict() for template in service.list_templates()]}

    @app.post("/api/templates")
    async def create_template(
        request: Request,
    ) -> dict[str, object]:
        payload = await read_text_payload(request)
        template = service.create_template(
            name=payload.get("name", "").strip() or "未命名模板",
            image_prompt=payload.get("image_prompt", "").strip() or loaded_settings.image_prompt,
            video_prompt=payload.get("video_prompt", "").strip() or loaded_settings.video_prompt,
        )
        return {"template": template.to_dict(), "message": "Template created."}

    @app.put("/api/templates/{template_id}")
    async def update_template(
        template_id: str,
        request: Request,
    ) -> dict[str, object]:
        payload = await read_text_payload(request)
        try:
            template = service.update_template(
                template_id,
                name=payload.get("name", "").strip() or "未命名模板",
                image_prompt=payload.get("image_prompt", "").strip() or loaded_settings.image_prompt,
                video_prompt=payload.get("video_prompt", "").strip() or loaded_settings.video_prompt,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"template": template.to_dict(), "message": "Template updated."}

    @app.delete("/api/templates/{template_id}")
    async def delete_template(template_id: str) -> dict[str, str]:
        try:
            service.delete_template(template_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"message": "Template deleted."}

    @app.post("/api/tasks")
    async def create_task(
        name: str = Form(...),
        image_prompt: str = Form(...),
        video_prompt: str = Form(...),
        template_id: str | None = Form(default=None),
        video_reference_image_path: str | None = Form(default=None),
        video_use_image_chat: str | None = Form(default="true"),
        reference_image: UploadFile | None = File(default=None),
    ) -> dict[str, object]:
        reference_image_path = loaded_settings.reference_image_path
        if reference_image is not None and reference_image.filename:
            suffix = Path(reference_image.filename).suffix or ".png"
            reference_image_path = UPLOADS_DIR / f"{uuid4().hex}{suffix}"
            reference_image_path.write_bytes(await reference_image.read())
        try:
            task = service.create_task(
                name=name.strip() or "未命名任务",
                image_prompt=image_prompt.strip() or loaded_settings.image_prompt,
                video_prompt=video_prompt.strip() or loaded_settings.video_prompt,
                reference_image_path=reference_image_path,
                template_id=(template_id or "").strip() or None,
                video_reference_image_path=(video_reference_image_path or "").strip() or None,
                video_use_image_chat=_parse_form_bool(video_use_image_chat, default=True),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"task": task.to_dict(), "message": "Task created."}

    @app.put("/api/tasks/{task_id}")
    async def update_task(
        task_id: str,
        name: str = Form(...),
        image_prompt: str = Form(...),
        video_prompt: str = Form(...),
        template_id: str | None = Form(default=None),
        video_reference_image_path: str | None = Form(default=None),
        video_use_image_chat: str | None = Form(default="true"),
        reference_image: UploadFile | None = File(default=None),
    ) -> dict[str, object]:
        reference_image_path: Path | None = None
        if reference_image is not None and reference_image.filename:
            suffix = Path(reference_image.filename).suffix or ".png"
            reference_image_path = UPLOADS_DIR / f"{uuid4().hex}{suffix}"
            reference_image_path.write_bytes(await reference_image.read())
        try:
            task = service.update_task(
                task_id,
                name=name.strip() or "未命名任务",
                image_prompt=image_prompt.strip() or loaded_settings.image_prompt,
                video_prompt=video_prompt.strip() or loaded_settings.video_prompt,
                reference_image_path=reference_image_path,
                template_id=(template_id or "").strip() or None,
                video_reference_image_path=(video_reference_image_path or "").strip() or None,
                video_use_image_chat=_parse_form_bool(video_use_image_chat, default=True),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"task": task.to_dict(), "message": "Task updated."}

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str) -> dict[str, str]:
        try:
            service.delete_task(task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Task deleted."}

    @app.post("/api/login")
    async def start_login() -> dict[str, str]:
        try:
            service.schedule_login()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Login flow started."}

    @app.post("/api/run-once")
    async def start_run_once(
        task_id: str = Form(...),
        image_prompt: str = Form(...),
        reference_image: UploadFile | None = File(default=None),
    ) -> dict[str, object]:
        reference_image_path: Path | None = None
        if reference_image is not None and reference_image.filename:
            suffix = Path(reference_image.filename).suffix or ".png"
            reference_image_path = UPLOADS_DIR / f"{uuid4().hex}{suffix}"
            reference_image_path.write_bytes(await reference_image.read())
        try:
            task = await service.run_once_now(
                task_id=task_id,
                image_prompt=image_prompt.strip() or loaded_settings.image_prompt,
                reference_image_path=reference_image_path,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Image generation completed.", "task": task.to_dict()}

    @app.post("/api/run-video")
    async def start_run_video(task_id: str = Form(...)) -> dict[str, object]:
        try:
            task = await service.submit_video_now(task_id=task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Video generation submitted.", "task": task.to_dict()}

    @app.get("/api/logs")
    async def get_logs(limit: int = 200) -> dict[str, object]:
        return {
            "path": str(get_app_log_path()),
            "lines": service.read_logs(limit=limit),
        }

    @app.post("/api/worker/start")
    async def start_worker() -> dict[str, str]:
        try:
            service.start_worker()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Worker started."}

    @app.post("/api/worker/stop")
    async def stop_worker() -> dict[str, str]:
        await service.stop_worker()
        return {"message": "Worker stopped."}

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIST_DIR / "index.html")

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(status_code=204)

    return app


def run_web_server() -> None:
    import uvicorn

    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "doubao_automation.web:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
