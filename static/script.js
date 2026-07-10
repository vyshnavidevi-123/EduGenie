// EduGenie frontend logic — tabs, API calls, result rendering.
(function () {
  "use strict";

  /* ---------- Tabs ---------- */

  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");

  const marginTips = {
    ask: "Ask a question the way you'd ask a classmate — EduGenie fills in the rest.",
    explain: "Pick the level that matches how it's been taught to you so far, not how advanced you want to sound.",
    quiz: "Generate a quiz right after reading a chapter — that's when self-testing sticks best.",
    summarize: "Paste in messy notes, not just clean text. EduGenie finds the exam-ready core.",
    path: "Add a goal, even a rough one — it changes which resources get recommended.",
  };

  function activatePanel(name) {
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.panel === name)));
    panels.forEach((p) => p.classList.toggle("is-active", p.id === `panel-${name}`));
    const note = document.getElementById("marginNote");
    if (note && marginTips[name]) {
      note.querySelector("p").textContent = marginTips[name];
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activatePanel(tab.dataset.panel));
  });

  /* ---------- Backend health check ---------- */

  async function checkHealth() {
    const dot = document.getElementById("statusDot");
    const label = document.getElementById("statusLabel");
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.gemini_configured) {
        dot.className = "status-dot ok";
        label.textContent = "Gemini connected";
      } else if (data.local_fallback_enabled) {
        dot.className = "status-dot warn";
        label.textContent = "using local fallback model";
      } else {
        dot.className = "status-dot error";
        label.textContent = "no AI backend configured";
      }
    } catch {
      dot.className = "status-dot error";
      label.textContent = "backend unreachable";
    }
  }
  checkHealth();

  /* ---------- Helpers ---------- */

  async function callApi(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    return data;
  }

  function setLoading(el, message) {
    el.hidden = false;
    el.className = "result is-loading";
    el.textContent = message;
  }

  function setError(el, message) {
    el.hidden = false;
    el.className = "result is-error";
    el.textContent = `Something went wrong: ${message}`;
  }

  function sourceBadge(source) {
    const label = source === "gemini" ? "Answered by Gemini" : "Answered by local model";
    return `<span class="result__source">${label}</span>`;
  }

  /* ---------- ASK ---------- */

  document.getElementById("form-ask").addEventListener("submit", async (e) => {
    e.preventDefault();
    const el = document.getElementById("result-ask");
    const question = document.getElementById("ask-question").value.trim();
    setLoading(el, "Thinking through your question…");
    try {
      const data = await callApi("/api/ask", { question });
      el.className = "result";
      el.innerHTML = `<div class="result__text"></div>${sourceBadge(data.source)}`;
      el.querySelector(".result__text").textContent = data.result;
    } catch (err) {
      setError(el, err.message);
    }
  });

  /* ---------- EXPLAIN ---------- */

  document.getElementById("form-explain").addEventListener("submit", async (e) => {
    e.preventDefault();
    const el = document.getElementById("result-explain");
    const concept = document.getElementById("explain-concept").value.trim();
    const level = document.getElementById("explain-level").value;
    setLoading(el, "Simplifying the concept…");
    try {
      const data = await callApi("/api/explain", { concept, level });
      el.className = "result";
      el.innerHTML = `<div class="result__text"></div>${sourceBadge(data.source)}`;
      el.querySelector(".result__text").textContent = data.result;
    } catch (err) {
      setError(el, err.message);
    }
  });

  /* ---------- QUIZ ---------- */

  document.getElementById("form-quiz").addEventListener("submit", async (e) => {
    e.preventDefault();
    const el = document.getElementById("result-quiz");
    const topic = document.getElementById("quiz-topic").value.trim();
    const num_questions = parseInt(document.getElementById("quiz-count").value, 10) || 5;
    const difficulty = document.getElementById("quiz-difficulty").value;
    setLoading(el, "Writing your quiz…");
    try {
      const data = await callApi("/api/quiz", { topic, num_questions, difficulty });
      el.className = "result";
      el.innerHTML = "";

      const grid = document.createElement("div");
      grid.className = "quiz-grid";
      const tpl = document.getElementById("tpl-quiz-card");

      data.questions.forEach((q, idx) => {
        const node = tpl.content.cloneNode(true);
        node.querySelector(".quiz-card__num").textContent = `Question ${idx + 1} of ${data.questions.length}`;
        node.querySelector(".quiz-card__question").textContent = q.question;

        const optionsEl = node.querySelector(".quiz-card__options");
        q.options.forEach((opt, i) => {
          const li = document.createElement("li");
          li.textContent = `${String.fromCharCode(65 + i)}. ${opt}`;
          optionsEl.appendChild(li);
        });

        const back = node.querySelector(".quiz-card__back");
        node.querySelector(".quiz-card__correct").textContent =
          `Correct answer: ${String.fromCharCode(65 + q.answer_index)}. ${q.options[q.answer_index]}`;
        node.querySelector(".quiz-card__explanation").textContent = q.explanation;

        const revealBtn = node.querySelector(".quiz-card__reveal");
        revealBtn.addEventListener("click", () => {
          back.hidden = !back.hidden;
          revealBtn.textContent = back.hidden ? "Reveal answer" : "Hide answer";
        });

        grid.appendChild(node);
      });

      el.appendChild(grid);
      const badge = document.createElement("div");
      badge.innerHTML = sourceBadge(data.source);
      el.appendChild(badge);
    } catch (err) {
      setError(el, err.message);
    }
  });

  /* ---------- SUMMARIZE ---------- */

  document.getElementById("form-summarize").addEventListener("submit", async (e) => {
    e.preventDefault();
    const el = document.getElementById("result-summarize");
    const text = document.getElementById("summarize-text").value.trim();
    const length = document.getElementById("summarize-length").value;
    setLoading(el, "Reading through your material…");
    try {
      const data = await callApi("/api/summarize", { text, length });
      el.className = "result";
      el.innerHTML = `<div class="result__text"></div>${sourceBadge(data.source)}`;
      el.querySelector(".result__text").textContent = data.result;
    } catch (err) {
      setError(el, err.message);
    }
  });

  /* ---------- LEARNING PATH ---------- */

  document.getElementById("form-path").addEventListener("submit", async (e) => {
    e.preventDefault();
    const el = document.getElementById("result-path");
    const topic = document.getElementById("path-topic").value.trim();
    const current_level = document.getElementById("path-level").value;
    const goal = document.getElementById("path-goal").value.trim() || null;
    setLoading(el, "Designing your roadmap…");
    try {
      const data = await callApi("/api/learning-path", { topic, current_level, goal });
      el.className = "result";
      el.innerHTML = "";

      data.stages.forEach((stage) => {
        const div = document.createElement("div");
        div.className = "path-stage";

        const h3 = document.createElement("h3");
        h3.textContent = stage.stage;
        div.appendChild(h3);

        const time = document.createElement("p");
        time.textContent = `Estimated time: ${stage.estimated_time}`;
        div.appendChild(time);

        const focusLabel = document.createElement("p");
        focusLabel.textContent = "Focus areas:";
        div.appendChild(focusLabel);

        const focusList = document.createElement("div");
        focusList.className = "tag-list";
        stage.focus_areas.forEach((f) => {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = f;
          focusList.appendChild(tag);
        });
        div.appendChild(focusList);

        const resourceLabel = document.createElement("p");
        resourceLabel.textContent = "Look for:";
        div.appendChild(resourceLabel);

        const resourceList = document.createElement("div");
        resourceList.className = "tag-list";
        stage.resources_to_seek.forEach((r) => {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = r;
          resourceList.appendChild(tag);
        });
        div.appendChild(resourceList);

        el.appendChild(div);
      });

      const badge = document.createElement("div");
      badge.innerHTML = sourceBadge(data.source);
      el.appendChild(badge);
    } catch (err) {
      setError(el, err.message);
    }
  });
})();
