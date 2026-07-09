"""
Functional tests for EduGenie.

These tests mock app.ai_service.generate() so the suite runs fast, free,
and offline — no real Gemini API key or network access required. This
covers the "Functional Testing" task (Epic 4) by exercising every route,
its request validation, and its response shape, including accounts and
saved history.

Run with:
    pip install pytest httpx sqlalchemy itsdangerous
    pytest tests/ -v
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Use an isolated, throwaway SQLite file for tests so we never touch the
# real edugenie.db used during local development.
TEST_DB_PATH = Path(__file__).resolve().parent / "test_edugenie.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.db import init_db  # noqa: E402

init_db()
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


# ---------------------------------------------------------------------------
# Accounts (signup / login / logout / me)
# ---------------------------------------------------------------------------

def test_me_returns_401_when_signed_out():
    anon_client = TestClient(app)  # fresh client, no cookies
    res = anon_client.get("/api/me")
    assert res.status_code == 401


def test_signup_login_logout_flow():
    signup_client = TestClient(app)

    res = signup_client.post(
        "/api/signup",
        json={"username": "asha", "email": "asha@example.com", "password": "hunter22"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "asha"

    # signing up should also sign the user in (session cookie set)
    res = signup_client.get("/api/me")
    assert res.status_code == 200
    assert res.json()["username"] == "asha"

    # duplicate signup should fail cleanly
    res = signup_client.post(
        "/api/signup",
        json={"username": "asha", "email": "someone-else@example.com", "password": "whatever1"},
    )
    assert res.status_code == 409

    # log out, then /api/me should be unauthorized again
    res = signup_client.post("/api/logout")
    assert res.status_code == 200
    res = signup_client.get("/api/me")
    assert res.status_code == 401

    # log back in with the right password
    res = signup_client.post(
        "/api/login", json={"username_or_email": "asha", "password": "hunter22"}
    )
    assert res.status_code == 200

    # wrong password should be rejected
    wrong_client = TestClient(app)
    res = wrong_client.post(
        "/api/login", json={"username_or_email": "asha", "password": "not-the-password"}
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# History (saved automatically when signed in)
# ---------------------------------------------------------------------------

def test_history_requires_login():
    anon_client = TestClient(app)
    res = anon_client.get("/api/history")
    assert res.status_code == 401


@patch("main.generate")
def test_history_is_empty_for_new_user_then_populates_after_a_query(mock_generate):
    hist_client = TestClient(app)
    hist_client.post(
        "/api/signup",
        json={"username": "ravi", "email": "ravi@example.com", "password": "letmein99"},
    )

    res = hist_client.get("/api/history")
    assert res.status_code == 200
    assert res.json()["items"] == []

    mock_generate.return_value = ("Photosynthesis converts light into energy.", "gemini")
    hist_client.post("/api/ask", json={"question": "What is photosynthesis?"})

    res = hist_client.get("/api/history")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["feature"] == "ask"
    assert "photosynthesis" in items[0]["input_text"].lower()


@patch("main.generate")
def test_history_not_saved_when_signed_out(mock_generate):
    anon_client = TestClient(app)
    mock_generate.return_value = ("An answer.", "gemini")
    res = anon_client.post("/api/ask", json={"question": "Anonymous question?"})
    assert res.status_code == 200  # request still succeeds
    # no session cookie was ever set, so there's nothing to check via
    # /api/history for this client -- it will correctly get a 401
    res = anon_client.get("/api/history")
    assert res.status_code == 401
