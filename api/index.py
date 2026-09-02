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

def render_template(request: Request, name: str):
    try:
        return templates.TemplateResponse(request, name, {"request": request})
    except TypeError:
        return templates.TemplateResponse(name, {"request": request})

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render_template(request, "index.html")

# Endpoint to serve the logo image at the root path expected by the monolithic template
from fastapi.responses import FileResponse
@app.get("/logo.png")
async def get_logo():
    logo_path = os.path.join(static_dir, "logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return HTMLResponse(status_code=404)

# All routes serve the monolithic index.html template
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request, "index.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return render_template(request, "index.html")

@app.get("/quoting", response_class=HTMLResponse)
async def quoting_page(request: Request):
    return render_template(request, "index.html")

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return render_template(request, "index.html")

# Healthcheck for Coolify / Docker Container monitoring
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "technical-water-system"}

# Catch-all route to serve monolithic SPA template for any direct URL navigation
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    return render_template(request, "index.html")
