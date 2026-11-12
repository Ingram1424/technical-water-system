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
import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

logger = logging.getLogger("railway_db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:TMJZIlYdlvVPojLLfKkPZWbkUEJEhNfS@yamabiko.proxy.rlwy.net:27667/railway"
)

def get_db_connection():
    import psycopg
    return psycopg.connect(DATABASE_URL)

def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        code TEXT PRIMARY KEY,
                        data JSONB NOT NULL,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                conn.commit()
        logger.info("Railway Postgres Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

@app.on_event("startup")
async def startup_event():
    init_db()

class UpsertPayload(BaseModel):
    code: str
    data: Dict[str, Any]

class BatchPayload(BaseModel):
    items: List[UpsertPayload]

@app.get("/api/db/status")
async def db_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM projects;")
                count = cur.fetchone()[0]
        return {"status": "connected", "database": "railway_postgres", "project_count": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/db/projects")
async def get_all_projects():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT code, data, updated_at FROM projects 
                    WHERE code NOT LIKE 'FILE:%' AND code NOT LIKE 'SHARE:%'
                    ORDER BY updated_at DESC;
                """)
                rows = cur.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "code": row[0],
                        "data": row[1] if isinstance(row[1], dict) else json.loads(row[1]),
                        "updated_at": row[2].isoformat() if row[2] else None
                    })
        return {"data": results, "error": None}
    except Exception as e:
        return {"data": None, "error": str(e)}

@app.get("/api/db/record/{code:path}")
async def get_record(code: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT code, data, updated_at FROM projects WHERE code = %s;", (code,))
                row = cur.fetchone()
                if row:
                    return {
                        "data": {
                            "code": row[0],
                            "data": row[1] if isinstance(row[1], dict) else json.loads(row[1]),
                            "updated_at": row[2].isoformat() if row[2] else None
                        },
                        "error": None
                    }
                return {"data": None, "error": "Not found"}
    except Exception as e:
        return {"data": None, "error": str(e)}

@app.post("/api/db/upsert")
async def upsert_record(payload: UpsertPayload):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                data_json = json.dumps(payload.data)
                cur.execute("""
                    INSERT INTO projects (code, data, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (code) DO UPDATE 
                    SET data = EXCLUDED.data, updated_at = NOW();
                """, (payload.code, data_json))
                conn.commit()
        return {"success": True, "code": payload.code}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/db/batch_sync")
async def batch_sync(payload: BatchPayload):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for item in payload.items:
                    data_json = json.dumps(item.data)
                    cur.execute("""
                        INSERT INTO projects (code, data, updated_at)
                        VALUES (%s, %s::jsonb, NOW())
                        ON CONFLICT (code) DO UPDATE 
                        SET data = EXCLUDED.data, updated_at = NOW();
                    """, (item.code, data_json))
                conn.commit()
        return {"success": True, "count": len(payload.items)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/db/record/{code:path}")
async def delete_record(code: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM projects WHERE code = %s;", (code,))
                conn.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
