# 🎬 CineTracker

A Flask + Supabase app for tracking movies you want to watch, marking them as watched, and rating them 1–5.

**Live app:** [cinetracker-watchlist-app.herokuapp.com](https://cinetracker-watchlist-app-d517f77cdcad.herokuapp.com/)

> Work in progress — actively being extended and refined.

## Features

- Email/password signup and login (via Supabase Auth)
- Add and remove movies from your watchlist
- Mark movies as watched / not watched
- Rate watched movies from 1 to 5
- Each user only sees and edits their own movies (enforced by Supabase Row Level Security)

## Tech Stack

- **Backend**: Flask (Python)
- **Database & Auth**: Supabase (Postgres + Auth)
- **Frontend**: Jinja templates, plain HTML/CSS
- **Hosting**: Heroku, auto-deployed from `main`

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root (this file is gitignored and should never be committed):
   ```dotenv
   SUPABASE_URL = "your-supabase-project-url"
   SUPABASE_KEY = "your-supabase-anon-public-key"
   SECRET_KEY = "a-long-random-string"
   ```
   - `SUPABASE_URL` / `SUPABASE_KEY` come from your Supabase project settings (use the `anon` public key, not the `service_role` key).
   - Generate `SECRET_KEY` with:
     ```bash
     python3 -c "import secrets; print(secrets.token_hex(32))"
     ```

3. In Supabase, create a `movies` table with (at minimum):
   - `id` (uuid or int, primary key)
   - `user_id` (uuid, references auth.users)
   - `title` (text)
   - `watched` (boolean, default false)
   - `rating` (int4, nullable)
   - `created_at` (timestamp, default now())

4. Enable Row Level Security on the `movies` table, with policies restricting `select`/`insert`/`update`/`delete` to rows where `auth.uid() = user_id`.

5. Run the app:
   ```bash
   python app.py
   ```
   Visit `http://127.0.0.1:5000`.

## Deployment

The app is deployed on Heroku with automatic deploys from GitHub — any push to `main` triggers a redeploy. Environment variables (`SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY`) are set directly in Heroku's config vars, not committed to the repo.

## Known limitations / next steps

- No token refresh — long-idle sessions require logging in again rather than silently refreshing.
- No dedicated "edit movie" page; rating and watched status are updated inline via dropdowns.
- No automated tests yet.
- Styling is functional but minimal — a polish pass is planned.

## Project structure

```
app.py            Flask routes (auth, movies CRUD)
database.py       Supabase client setup
Procfile          Heroku process definition
requirements.txt  Python dependencies
templates/
  base.html       Shared layout
  index.html      Watchlist page
  login.html      Login page
  signup.html     Signup page
static/
  css/main.css    Styling
```
