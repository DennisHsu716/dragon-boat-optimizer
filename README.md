# 🚣 Dragon Boat Optimizer

A Streamlit app for dragon boat teams to track paddler scores, rank
performance, and generate optimized boat lineups.

## Features

- **Multi-team accounts** — each team registers with a shared team
  name/password; all data is isolated per team in a SQLite database.
- **Upload / manual entry** — upload a roster+score CSV or enter time
  trial results manually. Supports both time-based and distance-based
  tests, with a configurable (safely sandboxed) scoring formula.
- **Rankings** — best-score leaderboards split by side (left/right) and
  gender.
- **Lineup optimizer** — generates a seat assignment that balances
  left/right power and weight, respects gender quotas, engine-row
  weighting, locked seats, and a designated caller/steer, using
  simulated annealing (`Project.py`).
- **Issue reporting** — teams can report bugs/feedback, stored per team.

## Project structure

```
app.py                     # Login / team registration gate + home menu
auth.py                    # Session helpers (require_login, logout, ...)
db.py                      # SQLite schema + all per-team data access
safe_eval.py                # Restricted AST-based evaluator for custom formulas
Project.py                  # Core seating/optimization logic (also runnable as a CLI)
pages/
  1_Upload_Data.py          # CSV upload + manual score entry
  2_Rank.py                 # Leaderboards
  3_Lineup.py                # Lineup generator
  4_Settings.py              # Settings menu
  5_Formula_Settings.py       # Scoring formula configuration
  6_Report_Issue.py           # Bug/feedback reporting
```

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`),
register a team, and start uploading data.

## Data & privacy

All team data (passwords, paddler names/weights, scores) lives in
`data/app.db`, a SQLite file created on first run. This directory is
git-ignored and never committed — don't remove it from `.gitignore`.

## Deploying

The app deploys as-is to [Streamlit Community
Cloud](https://share.streamlit.io) (point it at `app.py`). Note that
Community Cloud's filesystem is **not guaranteed persistent across
redeploys** — pushing new code rebuilds the container and wipes
`data/app.db`. Back up rankings via the "Download All Rankings CSV"
button before redeploying, or migrate to an external database (e.g.
Turso, Supabase) for production use.

## Command-line usage

`Project.py` can also be run standalone against a CSV + JSON config,
without the Streamlit UI:

```bash
python3 Project.py --csv paddlers.csv --config config.json
```
