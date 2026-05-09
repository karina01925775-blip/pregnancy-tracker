import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import get_db, engine, Base
from backend.auth import router as auth_router
print("ROUTER IMPORTED:", auth_router)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

print("\n=== REGISTERED ROUTES ===")
for route in app.routes:
    print(f"{route.path} -> {list(route.methods) if hasattr(route, 'methods') else 'Other'}")
print("=========================\n")

BASE_DIR = Path(__file__).resolve().parent.parent  # Корень проекта
STATIC_DIR = BASE_DIR / "app/static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

app.mount("/app/static", StaticFiles(directory=STATIC_DIR), name="static")

# Путь к папке шаблонов
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Создаём таблицы (после app = FastAPI()!)
Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")
#Для старта в терминале: uvicorn app.main:app --reload