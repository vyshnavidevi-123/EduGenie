"""
EduGenie — Google Gemini Powered Learning Assistant
FastAPI backend serving both the web UI and the JSON API.

Run with:
    uvicorn main:app --reload
"""
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from app import prompts, db, auth
from app.ai_service import generate, extract_json, AIServiceError
from app.config import settings
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
    UserOut,
)

app = FastAPI(
    title="EduGenie",
    description="Google Gemini Powered Learning Assistant",
    version="1.0.0",
)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, same_site="lax")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("startup")
async def on_startup():
    try:
        db.init_db()
    except db.DatabaseNotConfigured as exc:
        # Don't crash the whole app -- surface a clear error on first DB use instead
        # of a bare FUNCTION_INVOCATION_FAILED with no explanation.
        print(f"[EduGenie] WARNING: {exc}")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "has_gemini": settings.has_gemini},
    )


# ======================= Auth =======================

@app.post("/api/auth/signup", response_model=UserOut)
async def signup(request: Request, payload: SignupRequest):
    try:
        if db.get_user_by_email(payload.email):
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        password_hash = auth.hash_password(payload.password)
        user = db.create_user(payload.name.strip(), payload.email, password_hash)
    except db.DatabaseNotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    auth.login_user(request, user["id"])
    return UserOut(id=user["id"], name=user["name"], email=user["email"])


@app.post("/api/auth/login", response_model=UserOut)
async def login(request: Request, payload: LoginRequest):
    try:
        user = db.get_user_by_email(payload.email)
    except db.DatabaseNotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not user or not auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    auth.login_user(request, user["id"])
    return UserOut(id=user["id"], name=user["name"], email=user["email"])


@app.post("/api/auth/logout")
async def logout(request: Request):
    auth.logout_user(request)
    return {"status": "ok"}


@app.get("/api/auth/me")
async def me(request: Request):
    user = auth.current_user(request)
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "user": UserOut(id=user["id"], name=user["name"], email=user["email"])}


# ======================= History =======================

@app.get("/api/history")
async def get_history(request: Request):
    user = auth.require_user(request)
    rows = db.list_history(user["id"])
    return [
        {
            "id": r["id"],
            "tool": r["tool"],
            "input_summary": r["input_summary"],
            "result": r["result"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.delete("/api/history/{item_id}")
async def delete_history(request: Request, item_id: int):
    user = auth.require_user(request)
    ok = db.delete_history_item(user["id"], item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="History item not found.")
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": settings.has_gemini,
        "local_fallback_enabled": settings.ENABLE_LOCAL_FALLBACK,
    }


@app.post("/api/ask", response_model=GenericTextResponse)
async def ask(request: Request, payload: AskRequest):
    """Intelligent Question Answering."""
    user = auth.require_user(request)
    prompt = prompts.ASK_PROMPT.format(question=payload.question)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.add_history(user["id"], "ask", payload.question, text)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/explain", response_model=GenericTextResponse)
async def explain(request: Request, payload: ExplainRequest):
    """Simplified Concept Explanation."""
    user = auth.require_user(request)
    prompt = prompts.EXPLAIN_PROMPT.format(concept=payload.concept, level=payload.level)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.add_history(user["id"], "explain", payload.concept, text)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/quiz", response_model=QuizResponse)
async def quiz(request: Request, payload: QuizRequest):
    """AI-Powered Quiz Generation."""
    user = auth.require_user(request)
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

    db.add_history(user["id"], "quiz", payload.topic, text)
    return QuizResponse(topic=payload.topic, questions=questions, source=source)


@app.post("/api/summarize", response_model=GenericTextResponse)
async def summarize(request: Request, payload: SummarizeRequest):
    """Educational Text Summarization."""
    user = auth.require_user(request)
    prompt = prompts.SUMMARIZE_PROMPT.format(text=payload.text, length=payload.length)
    try:
        text, source = generate(prompt, max_local_tokens=768)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.add_history(user["id"], "summarize", payload.text[:120], text)
    return GenericTextResponse(result=text, source=source)


@app.post("/api/learning-path", response_model=LearningPathResponse)
async def learning_path(request: Request, payload: LearningPathRequest):
    """Personalized Learning Path Recommendations."""
    user = auth.require_user(request)
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

    db.add_history(user["id"], "learning-path", payload.topic, text)
    return LearningPathResponse(topic=payload.topic, stages=stages, source=source)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
