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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from app import prompts
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
)

app = FastAPI(
    title="EduGenie",
    description="Google Gemini Powered Learning Assistant",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


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
async def ask(payload: AskRequest):
    """Intelligent Question Answering."""
    prompt = prompts.ASK_PROMPT.format(question=payload.question)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GenericTextResponse(result=text, source=source)


@app.post("/api/explain", response_model=GenericTextResponse)
async def explain(payload: ExplainRequest):
    """Simplified Concept Explanation."""
    prompt = prompts.EXPLAIN_PROMPT.format(concept=payload.concept, level=payload.level)
    try:
        text, source = generate(prompt)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GenericTextResponse(result=text, source=source)


@app.post("/api/quiz", response_model=QuizResponse)
async def quiz(payload: QuizRequest):
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

    return QuizResponse(topic=payload.topic, questions=questions, source=source)


@app.post("/api/summarize", response_model=GenericTextResponse)
async def summarize(payload: SummarizeRequest):
    """Educational Text Summarization."""
    prompt = prompts.SUMMARIZE_PROMPT.format(text=payload.text, length=payload.length)
    try:
        text, source = generate(prompt, max_local_tokens=768)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GenericTextResponse(result=text, source=source)


@app.post("/api/learning-path", response_model=LearningPathResponse)
async def learning_path(payload: LearningPathRequest):
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

    return LearningPathResponse(topic=payload.topic, stages=stages, source=source)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
