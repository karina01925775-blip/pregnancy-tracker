from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Путь к папке шаблонов (строка!)
templates = Jinja2Templates(directory="app/templates")

context={"name": "Диана", "range_start": "2026-04-05", "range_end": "2026-04-15"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request= request, name="index.html", context={"name": context["name"],
                                                                                    "range_start": context["range_start"],
                                                                                    "range_end": context["range_end"]})

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")

#Для старта в терминале: uvicorn app.main:app --reload
