"""
EduGenie — Google Gemini Powered Learning Assistant
FastAPI backend serving both the web UI and the JSON API.

Run with:
    uvicorn main:app --reload
"""
import os
from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from app import prompts
from app.ai_service import generate, extract_json, AIServiceError
from app.auth import (
    get_current_user,
    get_optional_user,
    hash_password,
    verify_password,
    set_session_cookie,
    clear_session_cookie,
)
from app.config import settings
from app.db import get_db, init_db
from app.models_db import QueryLog, User
from app.schemas import (
    AskRequest,
    ExplainRequest,
    QuizRequest,
    QuizResponse,
    SummarizeRequest,
    LearningPathRequest,
    LearningPathResponse,
    GenericTextResponse,
    SignupRequest,
    LoginRequest,
    UserResponse,
    HistoryItem,
    HistoryResponse,
)

app = FastAPI(
    title="EduGenie",
    description="Google Gemini Powered Learning Assistant",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("startup")
def on_startup():
    # Never let a database hiccup take the whole app down -- accounts and
    # history are a bonus feature, not something that should block the
    # core Q&A/quiz/summarize/learning-path tools from working.
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] Database not available, accounts/history disabled: {exc}")


def log_history(db: Session, user: Optional[User], feature: str, input_text: str, source: str) -> None:
    if user is None:
        return
    try:
        entry = QueryLog(
            user_id=user.id,
            feature=feature,
            input_text=input_text[:500],
            output_source=source,
        )
        db.add(entry)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()  # history is best-effort; never break the actual answer


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "has_gemini": settings.has_gemini},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": settings.has_gemini,
        "local_fallback_enabled": settings.ENABLE_LOCAL_FALLBACK,
    }


@app.post("/api/ask", response_model=GenericTextResponse)
async def ask(
    payload: AskRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Intelligent Question Answering."""
    prompt = prompts.ASK_PROMPT.format(question=payload.question)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_history(db, user, "ask", payload.question, source)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/explain", response_model=GenericTextResponse)
async def explain(
    payload: ExplainRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Simplified Concept Explanation."""
    prompt = prompts.EXPLAIN_PROMPT.format(concept=payload.concept, level=payload.level)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_history(db, user, "explain", payload.concept, source)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/quiz", response_model=QuizResponse)
async def quiz(
    payload: QuizRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """AI-Powered Quiz Generation."""
    prompt = prompts.QUIZ_PROMPT.format(
        topic=payload.topic,
        num_questions=payload.num_questions,
        difficulty=payload.difficulty,
    )
    try:
        text, source = generate(prompt, max_local_tokens=1024)
        data = extract_json(text)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"The AI model returned a response that couldn't be parsed as a quiz: {exc}",
        ) from exc

    try:
        questions = data["questions"]
        for q in questions:
            if len(q["options"]) != 4:
                raise ValueError("Each question must have exactly 4 options.")
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502, detail=f"Malformed quiz data from the AI model: {exc}"
        ) from exc

    log_history(db, user, "quiz", payload.topic, source)
    return QuizResponse(topic=payload.topic, questions=questions, source=source)


@app.post("/api/summarize", response_model=GenericTextResponse)
async def summarize(
    payload: SummarizeRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Educational Text Summarization."""
    prompt = prompts.SUMMARIZE_PROMPT.format(text=payload.text, length=payload.length)
    try:
        text, source = generate(prompt, max_local_tokens=768)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_history(db, user, "summarize", payload.text[:120], source)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/learning-path", response_model=LearningPathResponse)
async def learning_path(
    payload: LearningPathRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Personalized Learning Path Recommendations."""
    prompt = prompts.LEARNING_PATH_PROMPT.format(
        topic=payload.topic,
        current_level=payload.current_level,
        goal=payload.goal or "general proficiency",
    )
    try:
        text, source = generate(prompt, max_local_tokens=1024)
        data = extract_json(text)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"The AI model returned a response that couldn't be parsed as a learning path: {exc}",
        ) from exc

    try:
        stages = data["stages"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502, detail=f"Malformed learning path data from the AI model: {exc}"
        ) from exc

    log_history(db, user, "learning_path", payload.topic, source)
    return LearningPathResponse(topic=payload.topic, stages=stages, source=source)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@app.post("/api/signup", response_model=UserResponse)
async def signup(payload: SignupRequest, response: Response, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="That username or email is already taken.")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That username or email is already taken.")
    db.refresh(user)

    set_session_cookie(response, user.id)
    return UserResponse(id=user.id, username=user.username, email=user.email)


@app.post("/api/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(
            (User.username == payload.username_or_email)
            | (User.email == payload.username_or_email)
        )
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password.")

    set_session_cookie(response, user.id)
    return UserResponse(id=user.id, username=user.username, email=user.email)


@app.post("/api/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"status": "ok"}


@app.get("/api/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, username=user.username, email=user.email)


@app.get("/api/history", response_model=HistoryResponse)
async def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = (
        db.query(QueryLog)
        .filter(QueryLog.user_id == user.id)
        .order_by(QueryLog.created_at.desc())
        .limit(50)
        .all()
    )
    items = [
        HistoryItem(
            id=e.id,
            feature=e.feature,
            input_text=e.input_text,
            output_source=e.output_source,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in entries
    ]
    return HistoryResponse(items=items)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
