# Campus Customs — Homework 4

A full-stack shop for **Campus Customs**, Yale's family-run merch store, with **Audrey**, an AI shopping assistant.

- **Frontend:** React + Vite + TypeScript. Home, About Us, Products (sort & filter sidebar), product pages, Log in / Create account, floating chat.
- **Backend:** Python FastAPI + a PydanticAI agent (`gpt-5.6-luna` via Portkey) that answers from the real database: honest prices and stock, chat search that updates the page, follow-up context, customer memory, safety guardrails, and an append-only audit trail.

## Folder structure

```
hw4/
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── frontend/                 # Vite React TypeScript app
├── backend/
│   ├── main.py               # FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py              # ┐
│   ├── models.py             # │ the agent: 4 files
│   ├── tools.py              # │
│   └── prompts/              # │
│       └── prompt.md         # ┘
└── output/
    ├── harness.md
    ├── design.md
    ├── usability.md
    ├── app_check.html
    ├── app_check_images/     # screenshots linked from app_check.html
    └── audit_trail.json
```

**Local-only data pack (not in git):**

```
data/
├── campus_customs.db
└── products/                 # images referenced by the catalogue
```

## How to run

### Step 1: Place the data pack

Put the data pack inside `hw4/` so you have `hw4/data/campus_customs.db` and `hw4/data/products/`. The backend won't start without it, and it tells you so.

### Step 2: Add your secrets

```bash
cp .env.example .env
```

Open `hw4/.env` and set `PORTKEY_API_KEY` (for the AI assistant) and `JWT_SECRET` (any long random string; `.env.example` shows a one-line command to make one).

### Step 3: Run the backend (Python 3.10+)

From `hw4/backend/`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r ../requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

- The API runs at http://localhost:8000 (docs at http://localhost:8000/docs).
- **First start takes ~30 seconds:** the backend makes white-background, same-size copies of the product photos in `data/products_web/`. Later starts are instant.

### Step 4: Run the frontend (Node 20.19+)

In a second terminal, from `hw4/frontend/`:

```bash
npm install
npm run dev
```

### Step 5: Open the site

Go to **http://localhost:5173**. Log in with the seed account `test@campuscustoms.yale.edu` / `password`, or create an account. Click **Chat** (bottom right) to talk to Audrey.

**Optional:** with both servers running and Google Chrome installed, `npm run app-check` (in `frontend/`) re-runs the live-site test and refreshes `output/app_check_images/`.

## Where to look

| File | What it covers |
|---|---|
| `output/harness.md` | The full system: how to run, architecture, database, accounts, the agent loop, all tools, every model field and why, safety rules, audit trail, specs and limits |
| `output/app_check.html` | Live-site test with screenshots: inventory in chat, chat search cards, sort & filter sidebar |
| `output/usability.md` | Usability improvements and why they help |
| `output/design.md` | Design choices (white + Yale blue, bulldogs, lingo) and why shoppers stay |
| `output/audit_trail.json` | Real agent-loop activity (append-only) |
| `AI_prompts.md` | Prompts and results for Problems 1–13 |
