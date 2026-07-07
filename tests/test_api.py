"""
Functional tests for EduGenie.

These tests mock app.ai_service.generate() so the suite runs fast, free,
and offline — no real Gemini API key or network access required. This
covers the "Functional Testing" task (Epic 4) by exercising every route,
its request validation, and its response shape.

Run with:
    pip install pytest httpx
    pytest tests/ -v
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "gemini_configured" in body
    assert "local_fallback_enabled" in body


def test_home_page_loads():
    res = client.get("/")
    assert res.status_code == 200
    assert "EduGenie" in res.text


# ---------------------------------------------------------------------------
# /api/ask
# ---------------------------------------------------------------------------

@patch("main.generate")
def test_ask_returns_answer(mock_generate):
    mock_generate.return_value = ("The Pacific Ocean is the largest ocean.", "gemini")
    res = client.post("/api/ask", json={"question": "Which is the largest ocean?"})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "gemini"
    assert "Pacific" in body["result"]


def test_ask_rejects_empty_question():
    res = client.post("/api/ask", json={"question": ""})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# /api/explain
# ---------------------------------------------------------------------------

@patch("main.generate")
def test_explain_returns_text(mock_generate):
    mock_generate.return_value = ("A right triangle explanation...", "gemini")
    res = client.post(
        "/api/explain", json={"concept": "Pythagoras Theorem", "level": "beginner"}
    )
    assert res.status_code == 200
    assert res.json()["result"]


# ---------------------------------------------------------------------------
# /api/quiz
# ---------------------------------------------------------------------------

VALID_QUIZ_JSON = json.dumps({
    "questions": [
        {
            "question": "What is a^2 + b^2 equal to in a right triangle?",
            "options": ["c", "c^2", "2c", "c/2"],
            "answer_index": 1,
            "explanation": "By the Pythagorean theorem, a^2 + b^2 = c^2.",
        }
    ]
})


@patch("main.generate")
def test_quiz_returns_valid_structure(mock_generate):
    mock_generate.return_value = (VALID_QUIZ_JSON, "gemini")
    res = client.post(
        "/api/quiz",
        json={"topic": "Pythagoras Theorem", "num_questions": 1, "difficulty": "easy"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["topic"] == "Pythagoras Theorem"
    assert len(body["questions"]) == 1
    q = body["questions"][0]
    assert len(q["options"]) == 4
    assert 0 <= q["answer_index"] < 4


@patch("main.generate")
def test_quiz_handles_malformed_model_output(mock_generate):
    mock_generate.return_value = ("not valid json at all", "gemini")
    res = client.post(
        "/api/quiz", json={"topic": "SQL", "num_questions": 3, "difficulty": "medium"}
    )
    assert res.status_code == 502


def test_quiz_rejects_out_of_range_question_count():
    res = client.post(
        "/api/quiz", json={"topic": "SQL", "num_questions": 50, "difficulty": "medium"}
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# /api/summarize
# ---------------------------------------------------------------------------

@patch("main.generate")
def test_summarize_returns_text(mock_generate):
    mock_generate.return_value = ("A concise summary.", "local-lamini")
    res = client.post(
        "/api/summarize",
        json={"text": "Long study notes about oceans and rivers.", "length": "short"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "local-lamini"
    assert body["result"]


# ---------------------------------------------------------------------------
# /api/learning-path
# ---------------------------------------------------------------------------

VALID_PATH_JSON = json.dumps({
    "stages": [
        {
            "stage": "Beginner: SQL Foundations",
            "focus_areas": ["SELECT statements", "filtering with WHERE"],
            "resources_to_seek": ["interactive SQL tutorial"],
            "estimated_time": "1-2 weeks",
        }
    ]
})


@patch("main.generate")
def test_learning_path_returns_valid_structure(mock_generate):
    mock_generate.return_value = (VALID_PATH_JSON, "gemini")
    res = client.post(
        "/api/learning-path",
        json={"topic": "SQL", "current_level": "beginner", "goal": "be job-ready"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["topic"] == "SQL"
    assert len(body["stages"]) == 1
    assert body["stages"][0]["stage"] == "Beginner: SQL Foundations"


# ---------------------------------------------------------------------------
# AI backend failure handling
# ---------------------------------------------------------------------------

@patch("main.generate")
def test_ask_returns_503_when_no_backend_available(mock_generate):
    from app.ai_service import AIServiceError

    mock_generate.side_effect = AIServiceError("No AI backend is available.")
    res = client.post("/api/ask", json={"question": "What is gravity?"})
    assert res.status_code == 503
