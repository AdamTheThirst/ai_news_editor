from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.routers.health import router as health_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Article Editor", debug=settings.app_env == "development")

    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(health_router)

    @application.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("auth/login.html", {"request": request})

    @application.exception_handler(403)
    def forbidden(request: Request, exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)

    @application.exception_handler(404)
    def not_found(request: Request, exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    @application.exception_handler(500)
    def server_error(request: Request, exc: Exception) -> HTMLResponse:
        return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)

    return application


app = create_app()
