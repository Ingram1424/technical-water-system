from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import json
import logging
import hmac
import hashlib
import base64
import time

logger = logging.getLogger("railway_db")

app = FastAPI()

# ---------------------------------------------------------------------------
# HTTP Security Headers Middleware (BUG-08, TC-SEC)
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "https://fonts.googleapis.com https://fonts.gstatic.com "
            "https://images.unsplash.com data: blob:; "
            "img-src 'self' data: blob: https:;"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Mount static folder
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

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:TMJZIlYdlvVPojLLfKkPZWbkUEJEhNfS@yamabiko.proxy.rlwy.net:27667/railway"
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

AUTH_SECRET = os.getenv("AUTH_SECRET", "tw-project-management-super-secret-key-2026")

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

# ---------------------------------------------------------------------------
# Authentication & Token Helpers (BUG-02, BUG-03, BUG-04, BUG-20, BUG-21)
# ---------------------------------------------------------------------------
DEFAULT_USERS = {
    "admin": {"password": "1234", "role": "admin", "displayName": "Super Admin"},
    "pm": {"password": "1234", "role": "pm", "displayName": "Project Manager"},
    "pm2": {"password": "1234", "role": "pm", "displayName": "Project Manager 2"},
    "accounting": {"password": "1234", "role": "accounting", "displayName": "Account System"}
}

def create_access_token(user_data: dict, expires_in_seconds: int = 86400 * 7) -> str:
    payload = {
        "username": user_data.get("username", "").lower(),
        "role": user_data.get("role", "customer"),
        "displayName": user_data.get("displayName") or user_data.get("name", ""),
        "userKey": user_data.get("userKey"),
        "exp": int(time.time()) + expires_in_seconds
    }
    raw = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"

def verify_access_token(token: str) -> Optional[dict]:
    if not token or "." not in token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64, sig = parts
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padding = 4 - (len(b64) % 4)
        if padding != 4:
            b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(b64.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

def get_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if "tw_token" in request.cookies:
        return request.cookies.get("tw_token", "")
    token = request.query_params.get("token")
    if token:
        return token
    return None

async def get_current_user_optional(request: Request) -> Optional[dict]:
    token = get_token_from_request(request)
    if not token:
        return None
    return verify_access_token(token)

async def get_current_user(request: Request) -> dict:
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def redact_financial_data(data: dict) -> dict:
    """Strip confidential cost and profit metrics for restricted roles (BUG-19)"""
    if not isinstance(data, dict):
        return data
    cleaned = dict(data)
    sensitive_keys = [
        "cost", "totalCost", "profit", "profitMargin", "expenses",
        "budget", "financials", "actualCost", "laborCost", "materialCost",
        "subcontractCost", "miscCost", "targetProfit", "projectedProfit"
    ]
    for k in sensitive_keys:
        cleaned.pop(k, None)
    return cleaned

def get_allowed_project_codes(user: dict) -> List[str]:
    """Retrieve allowed project codes for a user from FILE:USER_PERMISSIONS_DATA (BUG-12)"""
    role = user.get("role", "")
    if role in ["admin", "pm", "accounting"]:
        return []  # Empty means all allowed
    user_key = user.get("userKey")
    username = user.get("username", "").lower()
    allowed = set()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM projects WHERE code = 'FILE:USER_PERMISSIONS_DATA';")
                row = cur.fetchone()
                if row:
                    pdata = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    perms = pdata.get("permissions", {})
                    # Look up by userKey
                    user_perms = perms.get(user_key)
                    if not user_perms and username:
                        # Try finding key by username
                        cur.execute("SELECT data FROM projects WHERE code = 'FILE:CUSTOMER_ACCOUNTS_DATA';")
                        acc_row = cur.fetchone()
                        if acc_row:
                            acc_data = acc_row[0] if isinstance(acc_row[0], dict) else json.loads(acc_row[0])
                            for k, acc in acc_data.get("accounts", {}).items():
                                if (acc.get("username", "")).lower() == username:
                                    user_perms = perms.get(k)
                                    break
                    if user_perms and isinstance(user_perms, dict):
                        for p in user_perms.get("projects", []):
                            allowed.add(p)
    except Exception as e:
        logger.error(f"Error fetching user permissions: {e}")
    return list(allowed)

# ---------------------------------------------------------------------------
# Auth Endpoints (BUG-20, BUG-21, BUG-23)
# ---------------------------------------------------------------------------
class LoginPayload(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def auth_login(payload: LoginPayload):
    uname = payload.username.strip().lower()
    pwd = payload.password.strip()

    # 1. Check database accounts and static user overrides from FILE:CUSTOMER_ACCOUNTS_DATA
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM projects WHERE code = 'FILE:CUSTOMER_ACCOUNTS_DATA';")
                row = cur.fetchone()
                if row:
                    acc_doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    # Check static user password overrides (admin, pm, accounting)
                    overrides = acc_doc.get("staticUserOverrides", {})
                    if uname in DEFAULT_USERS:
                        expected_pwd = overrides.get(uname) or DEFAULT_USERS[uname]["password"]
                        if expected_pwd == pwd:
                            user_data = {
                                "username": uname,
                                "role": DEFAULT_USERS[uname]["role"],
                                "displayName": DEFAULT_USERS[uname]["displayName"],
                                "userKey": None
                            }
                            token = create_access_token(user_data)
                            return {"success": True, "token": token, "user": user_data}
                    
                    # Check dynamic database accounts (pe, tech, customer, etc.)
                    accounts = acc_doc.get("accounts", {})
                    for key, acc in accounts.items():
                        acc_uname = (acc.get("username") or "").strip().lower()
                        if acc_uname == uname:
                            if acc.get("password") == pwd:
                                role = acc.get("role") or "customer"
                                user_data = {
                                    "username": uname,
                                    "role": role,
                                    "displayName": acc.get("name") or uname,
                                    "userKey": acc.get("userKey") or key
                                }
                                token = create_access_token(user_data)
                                return {"success": True, "token": token, "user": user_data}
    except Exception as e:
        logger.error(f"Database error during login: {e}")

    # Fallback to default static accounts if database doesn't have overrides
    if uname in DEFAULT_USERS:
        target = DEFAULT_USERS[uname]
        if target["password"] == pwd:
            user_data = {
                "username": uname,
                "role": target["role"],
                "displayName": target["displayName"],
                "userKey": None
            }
            token = create_access_token(user_data)
            return {"success": True, "token": token, "user": user_data}

    raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

@app.get("/api/auth/verify")
@app.post("/api/auth/verify")
async def auth_verify(request: Request):
    user = await get_current_user(request)
    return {"valid": True, "user": user}

# ---------------------------------------------------------------------------
# Database API Models & Endpoints
# ---------------------------------------------------------------------------
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
async def get_all_projects(request: Request):
    # Require authentication (BUG-02)
    user = await get_current_user(request)
    role = user.get("role", "")

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

                # Scope checking for PE/Tech/Customer (BUG-12, BUG-13)
                is_restricted = role in ["pe", "tech", "technician", "customer"]
                allowed_codes = set(get_allowed_project_codes(user)) if is_restricted else None

                for row in rows:
                    pcode = row[0]
                    # Filter out projects outside permissions for restricted roles
                    if allowed_codes is not None and pcode not in allowed_codes:
                        continue

                    pdata = row[1] if isinstance(row[1], dict) else json.loads(row[1])

                    # Redact cost & profit for restricted roles (BUG-19)
                    if is_restricted:
                        pdata = redact_financial_data(pdata)

                    results.append({
                        "code": pcode,
                        "data": pdata,
                        "updated_at": row[2].isoformat() if row[2] else None
                    })
        return {"data": results, "error": None}
    except Exception as e:
        return {"data": None, "error": str(e)}

@app.get("/api/db/record/{code:path}")
async def get_record(code: str, request: Request):
    # Public & Share links bypass authentication for customer guest mode
    is_share = code.startswith("SHARE:") or code.startswith("sh_")
    user = await get_current_user_optional(request) if not is_share else None

    # Protect sensitive records: FILE:CUSTOMER_ACCOUNTS_DATA requires admin role (BUG-03, BUG-04)
    if code == "FILE:CUSTOMER_ACCOUNTS_DATA":
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden: Admin access required to view customer accounts")

    # If non-share record and unauthenticated, require login (BUG-02)
    if not is_share and not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT code, data, updated_at FROM projects WHERE code = %s;", (code,))
                row = cur.fetchone()
                if row:
                    pdata = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                    
                    # If user is restricted and viewing a project record, enforce IDOR permission check and redact financials (BUG-12, BUG-19)
                    if user and user.get("role") in ["pe", "tech", "technician", "customer"]:
                        if not code.startswith("FILE:") and not code.startswith("SHARE:") and not code.startswith("sh_"):
                            allowed_codes = get_allowed_project_codes(user)
                            if allowed_codes and code not in allowed_codes:
                                raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to access this project")
                            pdata = redact_financial_data(pdata)

                    # For customer accounts viewed by admin, mask plaintext passwords for safety (BUG-04)
                    if code == "FILE:CUSTOMER_ACCOUNTS_DATA" and isinstance(pdata, dict):
                        accs = pdata.get("accounts", {})
                        safe_accs = {}
                        for k, v in accs.items():
                            safe_item = dict(v)
                            # Never send plaintext password over API (BUG-04)
                            safe_item["password"] = "••••••••"
                            safe_item["password_masked"] = "••••••••"
                            safe_accs[k] = safe_item
                        pdata = dict(pdata)
                        pdata["accounts"] = safe_accs

                    return {
                        "data": {
                            "code": row[0],
                            "data": pdata,
                            "updated_at": row[2].isoformat() if row[2] else None
                        },
                        "error": None
                    }
                return {"data": None, "error": "Not found"}
    except HTTPException:
        raise
    except Exception as e:
        return {"data": None, "error": str(e)}

def merge_payload_data(code: str, existing_data: dict, new_data: dict) -> dict:
    if not isinstance(existing_data, dict):
        return new_data
    if not isinstance(new_data, dict):
        return new_data

    # Preserve existing password if updated with masked placeholder (BUG-04)
    if code == "FILE:CUSTOMER_ACCOUNTS_DATA":
        old_accs = existing_data.get("accounts", {})
        new_accs = new_data.get("accounts", {})
        if isinstance(old_accs, dict) and isinstance(new_accs, dict):
            for acc_k, acc_v in new_accs.items():
                if isinstance(acc_v, dict):
                    if acc_v.get("password") in ["••••••••", "********", "", None]:
                        if acc_k in old_accs and isinstance(old_accs[acc_k], dict) and "password" in old_accs[acc_k]:
                            acc_v["password"] = old_accs[acc_k]["password"]

    deleted_items = set(new_data.get("_deleted", [])) if isinstance(new_data.get("_deleted"), list) else set()

    # Deep merge top-level keys & union lists (BUG-06)
    merged = dict(existing_data)
    for k, v in new_data.items():
        if k == "_deleted":
            continue
        if isinstance(v, list) and isinstance(merged.get(k), list):
            # Array union preserving order
            combined = list(merged[k])
            for item in v:
                if item not in combined:
                    combined.append(item)
            if deleted_items:
                combined = [x for x in combined if x not in deleted_items]
            merged[k] = combined
        elif isinstance(v, dict) and isinstance(merged.get(k), dict):
            mdict = dict(merged[k])
            mdict.update(v)
            merged[k] = mdict
        else:
            merged[k] = v
    if "_deleted" in merged:
        del merged["_deleted"]
    return merged

@app.post("/api/db/upsert")
async def upsert_record(payload: UpsertPayload, request: Request):
    # Require authentication (BUG-05)
    user = await get_current_user(request)
    role = user.get("role", "")

    # Role permission checks on write
    if payload.code == "FILE:CUSTOMER_ACCOUNTS_DATA" and role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update user accounts")

    if not payload.code.startswith("FILE:") and not payload.code.startswith("SHARE:"):
        # Modifying project data: PE, Tech, Customer cannot modify project settings
        if role in ["tech", "technician", "customer"]:
            raise HTTPException(status_code=403, detail="Forbidden: Role not authorized to modify projects")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Concurrent update safety for central records: merge dictionary keys & union arrays (BUG-06)
                if payload.code.startswith("FILE:"):
                    cur.execute("SELECT data FROM projects WHERE code = %s;", (payload.code,))
                    existing_row = cur.fetchone()
                    if existing_row:
                        existing_data = existing_row[0] if isinstance(existing_row[0], dict) else json.loads(existing_row[0])
                        payload.data = merge_payload_data(payload.code, existing_data, payload.data)

                data_json = json.dumps(payload.data)
                cur.execute("""
                    INSERT INTO projects (code, data, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (code) DO UPDATE 
                    SET data = EXCLUDED.data, updated_at = NOW();
                """, (payload.code, data_json))
                conn.commit()
        return {"success": True, "code": payload.code}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/db/batch_sync")
async def batch_sync(payload: BatchPayload, request: Request):
    # Require authentication (BUG-05)
    user = await get_current_user(request)
    role = user.get("role", "")
    if role in ["tech", "technician", "customer"]:
        raise HTTPException(status_code=403, detail="Forbidden: Role not authorized for batch sync")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for item in payload.items:
                    item_data = item.data
                    if item.code.startswith("FILE:"):
                        cur.execute("SELECT data FROM projects WHERE code = %s;", (item.code,))
                        existing_row = cur.fetchone()
                        if existing_row:
                            existing_data = existing_row[0] if isinstance(existing_row[0], dict) else json.loads(existing_row[0])
                            item_data = merge_payload_data(item.code, existing_data, item_data)
                    data_json = json.dumps(item_data)
                    cur.execute("""
                        INSERT INTO projects (code, data, updated_at)
                        VALUES (%s, %s::jsonb, NOW())
                        ON CONFLICT (code) DO UPDATE 
                        SET data = EXCLUDED.data, updated_at = NOW();
                    """, (item.code, data_json))
                conn.commit()
        return {"success": True, "count": len(payload.items)}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/db/record/{code:path}")
async def delete_record(code: str, request: Request):
    # Require authentication (BUG-05)
    user = await get_current_user(request)
    role = user.get("role", "")

    # Only admin and pm can delete projects (BUG-05, BUG-14, BUG-18)
    if role not in ["admin", "pm"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only Admin and PM can delete records")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Cascade cleanup: delete project and all associated file attachments (BUG-31)
                file_prefix = f"FILE:{code}:%"
                cur.execute("""
                    DELETE FROM projects 
                    WHERE code = %s OR code LIKE %s;
                """, (code, file_prefix))
                conn.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

class BackupItem(BaseModel):
    code: str
    data: Any
    updated_at: Optional[str] = None

class BackupBatchPayload(BaseModel):
    items: list[BackupItem]

@app.post("/api/db/upload_backup_batch")
async def upload_backup_batch(payload: BackupBatchPayload, request: Request):
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {AUTH_SECRET}"
    if auth_header != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    count = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for item in payload.items:
                raw_data = item.data
                data_json = json.dumps(raw_data) if isinstance(raw_data, (dict, list)) else str(raw_data)
                cur.execute("""
                    INSERT INTO projects (code, data, updated_at)
                    VALUES (%s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
                    ON CONFLICT (code) DO UPDATE 
                    SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at;
                """, (item.code, data_json, item.updated_at))
                count += 1
            conn.commit()

    return {"success": True, "uploaded": count}

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

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "technical-water-system"}

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    return render_template(request, "index.html")
