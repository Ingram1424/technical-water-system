from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

# Mount static folder for local testing
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(parent_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates setup
templates_dir = os.path.join(parent_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "active_page": "login"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "active_project": ""
    })

@app.get("/quoting", response_class=HTMLResponse)
async def quoting_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "quoting",
        "active_project": ""
    })

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "projects",
        "active_project": ""
    })

@app.get("/project/info", response_class=HTMLResponse)
async def project_info_page(request: Request, project: str = ""):
    return templates.TemplateResponse("info.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "info"
    })

@app.get("/project/gantt", response_class=HTMLResponse)
async def project_gantt_page(request: Request, project: str = ""):
    return templates.TemplateResponse("gantt.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "gantt"
    })

@app.get("/project/actual", response_class=HTMLResponse)
async def project_actual_page(request: Request, project: str = ""):
    return templates.TemplateResponse("actual.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "actual"
    })

@app.get("/project/daily-report", response_class=HTMLResponse)
async def project_daily_page(request: Request, project: str = ""):
    return templates.TemplateResponse("daily_report.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "daily"
    })

@app.get("/project/photos", response_class=HTMLResponse)
async def project_photos_page(request: Request, project: str = ""):
    return templates.TemplateResponse("photos.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "photos"
    })

@app.get("/project/expenses", response_class=HTMLResponse)
async def project_expenses_page(request: Request, project: str = ""):
    return templates.TemplateResponse("expenses.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "expenses"
    })

@app.get("/project/documents", response_class=HTMLResponse)
async def project_documents_page(request: Request, project: str = ""):
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "active_page": "projects",
        "active_project": project,
        "active_subpage": "documents"
    })
