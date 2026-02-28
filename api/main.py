import re
import shutil
from html import escape as html_escape
from datetime import datetime
from pathlib import Path
import json
import os

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Path as ApiPath,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session, joinedload

try:
    from . import auth, models
    from .database import Base, SessionLocal, engine, get_db
except ImportError:  # pragma: no cover
    import auth
    import models
    from database import Base, SessionLocal, engine, get_db

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"
PROBLEMS_DIR = STORAGE_DIR / "problems"
SOLVERS_DIR = STORAGE_DIR / "solvers"
SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")

PROBLEM_CATEGORY_RULES: list[tuple[str, str]] = [
    ("calendar", "Scheduling"),
    ("schedule", "Scheduling"),
    ("planner", "Scheduling"),
    ("planning", "Scheduling"),
    ("timetable", "Scheduling"),
    ("workload", "Scheduling"),
    ("knapsack", "Combinatorial"),
    ("set_cover", "Combinatorial"),
    ("packing", "Combinatorial"),
    ("maxcut", "Graph"),
    ("graph", "Graph"),
    ("portfolio", "Portfolio"),
    ("tsp", "Routing"),
    ("route", "Routing"),
    ("vehicle", "Routing"),
    ("facility", "Routing"),
]

SOLVER_CATEGORY_RULES: list[tuple[str, str]] = [
    ("qubo", "QUBO"),
    ("qaoa", "Quantum"),
    ("quantum", "Quantum"),
    ("neal", "QUBO"),
    ("tabu", "Heuristic"),
    ("grasp", "Heuristic"),
    ("heuristic", "Heuristic"),
    ("baseline", "Heuristic"),
    ("highs", "MILP"),
    ("ortools", "MILP"),
    ("scip", "MILP"),
    ("mip", "MILP"),
    ("milp", "MILP"),
    ("qp", "QP"),
]

security = HTTPBearer(auto_error=False)
app = FastAPI(title="Rastion Hub API", version="0.1.0")

default_allow_origins = [
    "http://localhost:4321",
    "http://127.0.0.1:4321",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://leonidas1312.github.io",
]
raw_allow_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
configured_allow_origins = [origin.strip() for origin in raw_allow_origins.split(",") if origin.strip()]
allow_origins = configured_allow_origins or default_allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"^https://[a-zA-Z0-9-]+\.github\.io$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    avatar_url: str


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    description: str
    category: str | None = None
    download_count: int
    rating: float
    owner: UserOut


class SolverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    description: str
    category: str | None = None
    download_count: int
    rating: float
    owner: UserOut


class ProblemListResponse(BaseModel):
    items: list[ProblemOut]
    total: int
    page: int
    page_size: int


class SolverListResponse(BaseModel):
    items: list[SolverOut]
    total: int
    page: int
    page_size: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OAuthLoginUrlResponse(BaseModel):
    url: str


class TokenVerificationResponse(BaseModel):
    valid: bool
    user: UserOut | None = None


class RatePayload(BaseModel):
    rating: float = Field(ge=0.0, le=5.0)


class RateResponse(BaseModel):
    id: int
    item_type: str
    rating: float
    rating_count: int


def ensure_category_columns() -> None:
    inspector = inspect(engine)

    problem_columns = {column["name"] for column in inspector.get_columns("problems")}
    solver_columns = {column["name"] for column in inspector.get_columns("solvers")}

    with engine.begin() as connection:
        if "category" not in problem_columns:
            connection.execute(text("ALTER TABLE problems ADD COLUMN category VARCHAR"))
        if "category" not in solver_columns:
            connection.execute(text("ALTER TABLE solvers ADD COLUMN category VARCHAR"))


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_category_columns()
    backfill_missing_categories()
    PROBLEMS_DIR.mkdir(parents=True, exist_ok=True)
    SOLVERS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_name(raw: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", raw.strip()).strip("-.")
    return cleaned or "item"


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_manifest(manifest: str | None) -> dict[str, object]:
    raw = (manifest or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def infer_category(item_type: str, name: str, description: str, manifest: dict[str, object] | None = None) -> str:
    payload = manifest or {}

    explicit = normalize_optional_text(str(payload.get("category", "") or ""))
    if explicit:
        return explicit

    if item_type == "problem":
        optimization_class = normalize_optional_text(str(payload.get("optimization_class", "") or ""))
        if optimization_class:
            lowered = optimization_class.lower()
            if lowered in {"milp", "mip"}:
                return "Scheduling"
            if lowered == "qubo":
                return "Graph"
            if lowered == "qp":
                return "Portfolio"

    haystack = f"{name} {description}".lower()
    rules = PROBLEM_CATEGORY_RULES if item_type == "problem" else SOLVER_CATEGORY_RULES
    for token, category in rules:
        if token in haystack:
            return category

    return "General"


def backfill_missing_categories() -> None:
    with SessionLocal() as db:
        changed = 0

        uncategorized_problems = (
            db.query(models.Problem)
            .filter(or_(models.Problem.category.is_(None), models.Problem.category == ""))
            .all()
        )
        for problem in uncategorized_problems:
            problem.category = infer_category("problem", problem.name, problem.description)
            changed += 1

        uncategorized_solvers = (
            db.query(models.Solver)
            .filter(or_(models.Solver.category.is_(None), models.Solver.category == ""))
            .all()
        )
        for solver in uncategorized_solvers:
            solver.category = infer_category("solver", solver.name, solver.description)
            changed += 1

        if changed:
            db.commit()


def build_archive_path(item_type: str, user_id: int, name: str, version: str) -> Path:
    base = PROBLEMS_DIR if item_type == "problems" else SOLVERS_DIR
    return base / str(user_id) / sanitize_name(name) / f"{sanitize_name(version)}.zip"


def ensure_zip(upload: UploadFile) -> None:
    filename = upload.filename or ""
    if Path(filename).suffix.lower() != ".zip":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a .zip archive.",
        )


def persist_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with destination.open("wb") as out_file:
        shutil.copyfileobj(upload.file, out_file)


def archive_path_from_record(record_path: str | None) -> Path | None:
    if not record_path:
        return None
    candidate = APP_DIR / record_path
    return candidate if candidate.exists() else None


def remove_file_if_exists(path: Path | None) -> None:
    if path and path.exists():
        path.unlink()


def trim_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current != current.parent:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def callback_success_html(token: str, username: str) -> str:
    token_html = html_escape(token)
    username_html = html_escape(username)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Rastion Authorization</title>
    <style>
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        color: #0f172a;
        background: linear-gradient(140deg, #f8fafc, #e2e8f0);
      }}
      .shell {{
        max-width: 720px;
        margin: 4rem auto;
        background: white;
        border-radius: 14px;
        border: 1px solid #dbe3ef;
        box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
        padding: 1.6rem;
      }}
      h1 {{
        margin: 0 0 0.8rem;
        font-size: 1.5rem;
      }}
      p {{
        margin: 0.7rem 0;
      }}
      pre {{
        margin: 0.9rem 0;
        padding: 0.85rem;
        border-radius: 10px;
        background: #0f172a;
        color: #f8fafc;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-word;
      }}
      button {{
        border: 0;
        border-radius: 10px;
        background: #0f766e;
        color: white;
        padding: 0.6rem 1rem;
        font-size: 0.95rem;
        cursor: pointer;
      }}
      .hint {{
        color: #334155;
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <h1>Authorization successful</h1>
      <p>Signed in as <strong>{username_html}</strong>.</p>
      <p>Copy this token and paste it into your TUI:</p>
      <pre id="token">{token_html}</pre>
      <button id="copy-btn" type="button">Copy token</button>
      <p class="hint">After copying, return to the terminal and continue login.</p>
    </main>
    <script>
      document.getElementById("copy-btn").addEventListener("click", async () => {{
        const token = document.getElementById("token").textContent || "";
        try {{
          await navigator.clipboard.writeText(token);
          document.getElementById("copy-btn").textContent = "Copied";
        }} catch {{
          document.getElementById("copy-btn").textContent = "Copy failed";
        }}
      }});
    </script>
  </body>
</html>"""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    return await auth.authenticate_token(db, credentials.credentials)


@app.get("/auth/login", response_model=OAuthLoginUrlResponse)
async def login(request: Request):
    callback_url = str(request.url_for("callback"))
    return OAuthLoginUrlResponse(url=auth.build_github_oauth_url(redirect_uri=callback_url))


@app.get("/auth/callback", response_class=HTMLResponse)
async def callback(
    request: Request,
    code: str = Query(..., min_length=4),
    db: Session = Depends(get_db),
):
    callback_url = str(request.url_for("callback"))
    github_token = await auth.exchange_oauth_code_for_token(code=code, redirect_uri=callback_url)
    github_user = await auth.fetch_github_user(github_token)
    user = auth.upsert_user_from_github(db, github_user)
    return HTMLResponse(
        content=callback_success_html(github_token, user.username),
        headers={"Content-Disposition": "inline"},
    )


@app.post("/auth/token", response_model=TokenVerificationResponse)
async def verify_token(token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    raw_token = token.strip()
    if not raw_token:
        return TokenVerificationResponse(valid=False, user=None)

    try:
        user = await auth.authenticate_token(db, raw_token)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return TokenVerificationResponse(valid=False, user=None)
        raise
    return TokenVerificationResponse(valid=True, user=user)


@app.post("/auth/login", response_model=LoginResponse)
async def login_with_bearer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    github_user = await auth.fetch_github_user(credentials.credentials)
    user = auth.upsert_user_from_github(db, github_user)
    access_token = auth.create_access_token(str(user.id))
    return LoginResponse(access_token=access_token, user=user)


@app.get("/auth/me", response_model=UserOut)
async def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/problems", response_model=ProblemListResponse)
def list_problems(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized_category = normalize_optional_text(category)
    query = (
        db.query(models.Problem)
        .options(joinedload(models.Problem.owner))
        .order_by(models.Problem.created_at.desc())
    )

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Problem.name.ilike(like),
                models.Problem.description.ilike(like),
            )
        )

    if normalized_category:
        query = query.filter(models.Problem.category == normalized_category)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return ProblemListResponse(items=items, total=total, page=page, page_size=page_size)


@app.post("/problems", response_model=ProblemOut, status_code=status.HTTP_201_CREATED)
async def upload_problem(
    name: str = Form(..., min_length=1, max_length=120),
    version: str = Form(..., min_length=1, max_length=60),
    description: str = Form("", max_length=5000),
    category: str | None = Form(None, max_length=120),
    manifest: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    manifest_payload = parse_manifest(manifest)
    normalized_category = normalize_optional_text(category) or infer_category(
        "problem",
        name=name,
        description=description,
        manifest=manifest_payload,
    )
    ensure_zip(file)

    existing = (
        db.query(models.Problem)
        .filter(
            models.Problem.owner_id == current_user.id,
            models.Problem.name == name,
            models.Problem.version == version,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Benchmark with this name and version already exists for this user.",
        )

    archive_path = build_archive_path("problems", current_user.id, name, version)

    problem = models.Problem(
        owner_id=current_user.id,
        name=name,
        version=version,
        description=description,
        category=normalized_category,
        created_at=datetime.utcnow(),
    )

    try:
        persist_upload(file, archive_path)

        db.add(problem)
        db.flush()

        version_record = models.ProblemVersion(
            problem_id=problem.id,
            version=version,
            description=description,
            file_path=str(archive_path.relative_to(APP_DIR)),
            created_at=datetime.utcnow(),
        )
        db.add(version_record)
        db.commit()
    except Exception:
        db.rollback()
        remove_file_if_exists(archive_path)
        raise

    db.refresh(problem)
    return (
        db.query(models.Problem)
        .options(joinedload(models.Problem.owner))
        .filter(models.Problem.id == problem.id)
        .one()
    )


@app.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = (
        db.query(models.Problem)
        .options(joinedload(models.Problem.owner))
        .filter(models.Problem.id == problem_id)
        .first()
    )
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found.")
    return problem


@app.get("/problems/{problem_id}/download")
def download_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = db.query(models.Problem).filter(models.Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found.")

    version_record = (
        db.query(models.ProblemVersion)
        .filter(
            models.ProblemVersion.problem_id == problem.id,
            models.ProblemVersion.version == problem.version,
        )
        .order_by(models.ProblemVersion.created_at.desc())
        .first()
    )

    archive_path = archive_path_from_record(version_record.file_path if version_record else None)
    if archive_path is None:
        archive_path = build_archive_path("problems", problem.owner_id, problem.name, problem.version)

    if not archive_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found.")

    problem.download_count += 1
    db.add(problem)
    db.commit()

    filename = f"{sanitize_name(problem.name)}-{sanitize_name(problem.version)}.zip"
    return FileResponse(path=archive_path, media_type="application/zip", filename=filename)


@app.delete("/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(
    problem_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    problem = (
        db.query(models.Problem)
        .options(joinedload(models.Problem.versions))
        .filter(models.Problem.id == problem_id)
        .first()
    )
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found.")
    if problem.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required.")

    fallback_archive = build_archive_path("problems", problem.owner_id, problem.name, problem.version)
    removed_any = False
    for version in problem.versions:
        version_path = archive_path_from_record(version.file_path)
        remove_file_if_exists(version_path)
        removed_any = removed_any or bool(version_path)

    if not removed_any:
        remove_file_if_exists(fallback_archive)

    db.delete(problem)
    db.commit()

    trim_empty_parents(fallback_archive.parent, PROBLEMS_DIR)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/solvers", response_model=SolverListResponse)
def list_solvers(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized_category = normalize_optional_text(category)
    query = (
        db.query(models.Solver)
        .options(joinedload(models.Solver.owner))
        .order_by(models.Solver.created_at.desc())
    )

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Solver.name.ilike(like),
                models.Solver.description.ilike(like),
            )
        )

    if normalized_category:
        query = query.filter(models.Solver.category == normalized_category)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return SolverListResponse(items=items, total=total, page=page, page_size=page_size)


@app.post("/solvers", response_model=SolverOut, status_code=status.HTTP_201_CREATED)
async def upload_solver(
    name: str = Form(..., min_length=1, max_length=120),
    version: str = Form(..., min_length=1, max_length=60),
    description: str = Form("", max_length=5000),
    category: str | None = Form(None, max_length=120),
    manifest: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    manifest_payload = parse_manifest(manifest)
    normalized_category = normalize_optional_text(category) or infer_category(
        "solver",
        name=name,
        description=description,
        manifest=manifest_payload,
    )
    ensure_zip(file)

    existing = (
        db.query(models.Solver)
        .filter(
            models.Solver.owner_id == current_user.id,
            models.Solver.name == name,
            models.Solver.version == version,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solver with this name and version already exists for this user.",
        )

    archive_path = build_archive_path("solvers", current_user.id, name, version)

    solver = models.Solver(
        owner_id=current_user.id,
        name=name,
        version=version,
        description=description,
        category=normalized_category,
        created_at=datetime.utcnow(),
    )

    try:
        persist_upload(file, archive_path)

        db.add(solver)
        db.flush()

        version_record = models.SolverVersion(
            solver_id=solver.id,
            version=version,
            description=description,
            file_path=str(archive_path.relative_to(APP_DIR)),
            created_at=datetime.utcnow(),
        )
        db.add(version_record)
        db.commit()
    except Exception:
        db.rollback()
        remove_file_if_exists(archive_path)
        raise

    db.refresh(solver)
    return (
        db.query(models.Solver)
        .options(joinedload(models.Solver.owner))
        .filter(models.Solver.id == solver.id)
        .one()
    )


@app.get("/solvers/{solver_id}", response_model=SolverOut)
def get_solver(solver_id: int, db: Session = Depends(get_db)):
    solver = (
        db.query(models.Solver)
        .options(joinedload(models.Solver.owner))
        .filter(models.Solver.id == solver_id)
        .first()
    )
    if not solver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solver not found.")
    return solver


@app.get("/solvers/{solver_id}/download")
def download_solver(solver_id: int, db: Session = Depends(get_db)):
    solver = db.query(models.Solver).filter(models.Solver.id == solver_id).first()
    if not solver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solver not found.")

    version_record = (
        db.query(models.SolverVersion)
        .filter(
            models.SolverVersion.solver_id == solver.id,
            models.SolverVersion.version == solver.version,
        )
        .order_by(models.SolverVersion.created_at.desc())
        .first()
    )

    archive_path = archive_path_from_record(version_record.file_path if version_record else None)
    if archive_path is None:
        archive_path = build_archive_path("solvers", solver.owner_id, solver.name, solver.version)

    if not archive_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found.")

    solver.download_count += 1
    db.add(solver)
    db.commit()

    filename = f"{sanitize_name(solver.name)}-{sanitize_name(solver.version)}.zip"
    return FileResponse(path=archive_path, media_type="application/zip", filename=filename)


@app.delete("/solvers/{solver_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_solver(
    solver_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    solver = (
        db.query(models.Solver)
        .options(joinedload(models.Solver.versions))
        .filter(models.Solver.id == solver_id)
        .first()
    )
    if not solver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solver not found.")
    if solver.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required.")

    fallback_archive = build_archive_path("solvers", solver.owner_id, solver.name, solver.version)
    removed_any = False
    for version in solver.versions:
        version_path = archive_path_from_record(version.file_path)
        remove_file_if_exists(version_path)
        removed_any = removed_any or bool(version_path)

    if not removed_any:
        remove_file_if_exists(fallback_archive)

    db.delete(solver)
    db.commit()

    trim_empty_parents(fallback_archive.parent, SOLVERS_DIR)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/{item_type}/{item_id}/rate", response_model=RateResponse)
def rate_item(
    item_type: str = ApiPath(..., description="benchmark/benchmarks or solver/solvers"),
    item_id: int = ApiPath(..., ge=1),
    payload: RatePayload = Body(...),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = item_type.lower().strip()

    if normalized in {"problem", "problems", "benchmark", "benchmarks"}:
        item = db.query(models.Problem).filter(models.Problem.id == item_id).first()
        tag = "benchmark"
    elif normalized in {"solver", "solvers"}:
        item = db.query(models.Solver).filter(models.Solver.id == item_id).first()
        tag = "solver"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type must be benchmark/benchmarks or solver/solvers.",
        )

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

    count = int(item.rating_count or 0)
    current_score = float(item.rating or 0.0)

    item.rating = ((current_score * count) + payload.rating) / (count + 1)
    item.rating_count = count + 1

    db.add(item)
    db.commit()
    db.refresh(item)

    return RateResponse(
        id=item.id,
        item_type=tag,
        rating=round(item.rating, 4),
        rating_count=item.rating_count,
    )
