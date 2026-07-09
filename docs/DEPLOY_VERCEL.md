# Deploying EduGenie: GitHub → Vercel

## 1. Push to GitHub

```bash
cd edugenie
git init
git add .
git commit -m "Initial commit: EduGenie learning assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `__pycache__/`, and `.vercel/` so you
won't accidentally commit secrets or local build artifacts.

## 2. Import into Vercel

1. Go to https://vercel.com/new
2. Import the GitHub repository you just pushed.
3. Vercel will auto-detect it as a Python project because it finds
   `requirements.txt` and a FastAPI `app` instance in `main.py` — no
   framework preset needs to be selected manually.
4. **Before deploying**, add your environment variables:
   - Go to the project's **Settings → Environment Variables**
   - Add `GEMINI_API_KEY` with your real key (from
     https://aistudio.google.com/app/apikey)
   - Optionally add `GEMINI_MODEL` (defaults to `gemini-2.5-flash`)
   - Set `ENABLE_LOCAL_FALLBACK=false` — the local model isn't installed in
     this deployment (see below), so leaving this on just adds a confusing
     error message if Gemini ever fails; `false` gives a clean error instead.
   - Add `SECRET_KEY` — any long random string (`openssl rand -hex 32`),
     used to sign login sessions.
   - Add `DATABASE_URL` — see step 3.5 below. Accounts/history won't work
     without this, but the 5 core AI tools still will.
5. Click **Deploy**.

## 3.5. Set up the database (for accounts + saved history)

Vercel's filesystem doesn't persist between requests, so the SQLite file
used in local development won't work in production. Instead:

1. In your Vercel project, go to **Storage → Create Database → Postgres**
   (this is powered by Neon and has a free tier).
2. Once created, Vercel usually offers to connect it to your project and
   inject the connection string automatically as an environment variable
   (commonly `POSTGRES_URL` or `DATABASE_URL`).
3. If it's added as `POSTGRES_URL` rather than `DATABASE_URL`, go back to
   **Settings → Environment Variables** and add `DATABASE_URL` with the
   same value, since that's the variable EduGenie's code reads.
4. Redeploy after adding it (see step 6 below) — env vars only apply to
   new deployments.

Tables are created automatically the first time the app starts — no
migration command to run.

## 3. Why the local fallback model is disabled here

This repo ships **two** requirements files:

- `requirements.txt` — lean, Gemini-only. This is what Vercel installs by
  default.
- `requirements-local-fallback.txt` — adds `torch` + `transformers` for the
  offline LaMini-Flan-T5 fallback. **Not used on Vercel.**

Vercel's Python functions cap the deployed bundle at 500MB uncompressed;
torch + transformers alone routinely exceed that, and reloading a
multi-hundred-MB model on every cold start would be slow anyway. So the
production deployment is Gemini-only — make sure `GEMINI_API_KEY` is set,
since there's no fallback if it's missing.

If you want the local fallback for offline development, install it
separately on your own machine:
```bash
pip install -r requirements.txt -r requirements-local-fallback.txt
```

## 6. Verify the deployment

Once deployed, Vercel gives you a URL like `https://your-project.vercel.app`.

- Open it in a browser — you should see the EduGenie UI.
- Check `https://your-project.vercel.app/api/health` — it should return
  `"gemini_configured": true`.
- Try one request from each tab (Ask, Explain, Quiz, Summarize, Learning
  Path) to confirm Gemini responses are working end-to-end.

## 7. Custom domain (optional)

In the Vercel project, go to **Settings → Domains** and add your own
domain — Vercel handles DNS/SSL automatically once you point your
domain's records at it as instructed there.

## Notes / limitations on Vercel

- **Stateless**: no database is used, so this isn't affected by
  serverless cold starts losing memory — every request is independent by
  design (see `docs/ER_DIAGRAM.md` if you later add persistence, which
  would need an external DB like Neon/Supabase Postgres, not local SQLite,
  since Vercel's filesystem is ephemeral).
- **Timeouts**: `vercel.json` sets `maxDuration: 60` seconds. This requires
  a Pro or Enterprise plan to take effect above the Hobby plan's default;
  on Hobby, functions are capped lower. If Gemini responses are timing out
  on a slow request (e.g. a long quiz), either upgrade your plan or reduce
  `num_questions`.
- **Cold starts**: the first request after inactivity may take a bit
  longer while the function spins up — this is normal for serverless.
