# PR Chronicler — Open-Source Contribution Explorer & Outreach Platform

PR Chronicler is an AI-powered Open-Source Contribution Explorer, Reflection Engine, and Outreach Platform.

It provides two primary workflows:

1. **Manual GitHub Contribution Explorer & Outreach Platform**:
   - Enter any GitHub username, profile URL (`https://github.com/username`), or repository URL (`https://github.com/owner/repo`).
   - Discover a contributor's public open-source contributions, authored pull requests (merged, open, closed), and public repositories.
   - Inspect code changes, diff patches, problem statements, and linked issues.
   - Generate on-demand, evidence-grounded AI engineering reflections powered by Gemini and LangChain LCEL (Issue Details, Execution Summary, and 3–4 Key Learnings distinguishing `[Verified]` code facts from `[Inferred]` intent).
   - Draft and dispatch personalized outreach emails using verified public profile emails or user-provided addresses, with full previews, explicit confirmation safeguards, and masked recipient privacy.

2. **Automated Merged-PR Webhook Engine**:
   - Listens on `POST /webhook/github` with HMAC-SHA256 signature verification.
   - Filters strictly for successfully closed and merged pull requests.
   - Automatically hydrates context, generates structured Gemini post-mortems, and dispatches formatted HTML reports via SMTP.
   - Tracks delivery idempotency, status transitions, and audit records in SQLite WAL mode.

---

## Architecture Overview

```
                                      +--------------------------+
                                      |   GitHub Webhook Event   |
                                      +-------------+------------+
                                                    |
                                                    v
                                      +-------------+------------+
                                      | POST /webhook/github     |
                                      | - HMAC SHA-256 Check     |
                                      | - Action == 'closed'     |
                                      | - Merged == True         |
                                      +-------------+------------+
                                                    |
                         +--------------------------+--------------------------+
                         | (Ignored: opened, synch, unmerged)                  | (Merged Event Accepted)
                         v                                                     v
          +------------------------------+                       +-----------------------------+
          | HTTP 200 (Audit IGNORED)     |                       | SQLite Idempotency Check    |
          | No downstream pipeline run   |                       +--------------+--------------+
          +------------------------------+                                      |
                                                                                v
                                                                 +-----------------------------+
                                                                 | GitHub Context Hydration    |
                                                                 | - PR metadata & files       |
                                                                 | - Patch diffs (pagination)  |
                                                                 | - Linked issues (Regex)     |
                                                                 +--------------+--------------+
                                                                                |
                                                                                v
                                                                 +-----------------------------+
                                                                 | LangChain LCEL + Gemini     |
                                                                 | - Prompt Grounding          |
                                                                 | - Strict Pydantic Validator |
                                                                 | - 3-4 Key Learnings         |
                                                                 +--------------+--------------+
                                                                                |
                                                                                v
                                                                 +-----------------------------+
                                                                 | SMTP Dispatcher             |
                                                                 | - Off event loop (Thread)   |
                                                                 | - TLS / SSL Support         |
                                                                 | - Plain Text & HTML Body    |
                                                                 +--------------+--------------+
                                                                                |
                                                                                v
                                                                 +-----------------------------+
                                                                 | DB Status: COMPLETED        |
                                                                 | Dual Observability Logging  |
                                                                 +-----------------------------+
```

---

## Project Structure

```text
pr-chronicler/
├── app/
│   ├── __init__.py           # Application package
│   ├── main.py               # FastAPI entrypoint, lifespan context & health checks
│   ├── config.py             # Pydantic BaseSettings loading from .env
│   ├── models.py             # Pydantic schemas (GitHub payloads, context, ReflectionOutput)
│   ├── database.py           # Durable SQLite tracking & idempotency manager
│   ├── webhook.py            # POST /webhook/github endpoint, signature & filter logic
│   ├── github_client.py      # Async GitHub REST client with pagination & issue parsing
│   ├── reflection_chain.py   # LangChain LCEL pipeline with Gemini & JsonOutputParser
│   ├── email_dispatcher.py   # SMTP emailer with TLS and thread-offloading
│   └── logging_config.py     # Dual console & file logger with credential sanitizer
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Shared test fixtures & SQLite temp databases
│   ├── test_webhook.py       # Signature verification, event filtering & routing tests
│   ├── test_github_client.py # Pagination, linked issues, rate limits & diff character counting
│   ├── test_reflection_chain.py # LCEL execution, prompt formatting & Pydantic constraints
│   ├── test_email_dispatcher.py # Subject format, body structure, TLS & auth security
│   └── test_idempotency.py   # SQLite status transitions, duplicate suppression & retry
├── simulate_merge.py         # CLI test utility to simulate GitHub webhook deliveries
├── requirements.txt          # Python dependencies
├── .env.example              # Documented environment variable template
├── .gitignore                # Git ignore for venvs, secrets, databases, logs
├── README.md                 # Project documentation
└── pr_chronicler.log         # Dual logging output file
```

---

## Requirements and Installation

### 1. Prerequisites
- Python 3.9+ (Python 3.10+ recommended)
- `pip` package manager

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Google AI Studio Gemini API Key | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini Model ID | `gemini-1.5-flash` |
| `GEMINI_TEMPERATURE` | Sampling temperature | `0.1` |
| `GITHUB_TOKEN` | GitHub Personal Access Token (for rate limits) | `ghp_...` |
| `GITHUB_WEBHOOK_SECRET` | HMAC SHA-256 Webhook secret | `your-secret-key` |
| `SMTP_EMAIL` | Sender email address | `bot@gmail.com` |
| `SMTP_APP_PASSWORD` | App Password (e.g. Gmail 2FA App Password) | `abcd efgh ijkl mnop` |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` (TLS) or `465` (SSL) |
| `SMTP_USE_TLS` | Enable STARTTLS | `true` |
| `RECIPIENT_EMAIL` | Target email for PR reflections | `team@example.com` |
| `DATABASE_PATH` | Local SQLite database file | `pr_chronicler.db` |
| `LOG_FILE` | Log file destination | `pr_chronicler.log` |

---

## Verifying Compatible Gemini Models

To discover and verify which Gemini models are supported by the installed `langchain-google-genai` integration:

```bash
python -c "
import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('GOOGLE_API_KEY')
if key:
    genai.configure(api_key=key)
    print('Supported Gemini Models with generateContent capability:')
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f' - {m.name}')
else:
    print('Currently supported default model identifier: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash')
"
```

---

## Running the Application

### Start the FastAPI Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Health Check
Verify the service is running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "pr_chronicler.db",
  "gemini_model": "gemini-1.5-flash",
  "gemini_configured": true,
  "smtp_configured": true,
  "github_token_configured": true,
  "webhook_secret_enforced": true
}
```

Interactive API documentation is available at: `http://localhost:8000/docs`.

---

## Running the Test Suite

Execute the automated test suite covering all functional acceptance criteria:

```bash
PYTHONPATH=. pytest -v
```

All 31 unit and integration tests mock external services (GitHub API, Gemini LLM, SMTP) without requiring real credentials or sending actual emails:
- `test_webhook.py`: Webhook filtering, ignored action safety, signature enforcement, malformed JSON.
- `test_github_client.py`: Pagination of changed files, linked issue regex parsing, diff character counting, error handling.
- `test_reflection_chain.py`: LCEL pipeline, strict Pydantic validation (3-4 key learnings requirement), fallback grounding.
- `test_email_dispatcher.py`: Exact subject format `[OS-Log] PR Merged: <Repository Name> (#<PR Number>)`, body formatting, TLS/SSL, credential sanitization.
- `test_idempotency.py`: SQLite transaction locking, duplicate suppression, retry of failed deliveries.

---

## Webhook Simulation Utility (`simulate_merge.py`)

A built-in CLI utility allows you to simulate mock or real GitHub webhook deliveries against `http://localhost:8000/webhook/github`:

### 1. Merged PR (Triggers Pipeline)
```bash
python simulate_merge.py --scenario merged --pr 42
```

### 2. Closed but Unmerged PR (Safely Ignored)
```bash
python simulate_merge.py --scenario unmerged --pr 43
```
*Expected: Returns HTTP 200 with `status: ignored`, pipeline is not invoked.*

### 3. Opened or Synchronize PR (Safely Ignored)
```bash
python simulate_merge.py --scenario opened --pr 44
python simulate_merge.py --scenario synchronize --pr 44
```
*Expected: Returns HTTP 200 with `status: ignored`, pipeline is not invoked.*

### 4. Testing HMAC Signature Verification
If `GITHUB_WEBHOOK_SECRET` is configured in `.env`, supply the matching key:
```bash
python simulate_merge.py --scenario merged --secret "your-secret-key"
```

### 5. Testing Idempotency and Deduplication
Send the same delivery UUID twice:
```bash
python simulate_merge.py --scenario merged --delivery-id "unique-delivery-uuid-101"
python simulate_merge.py --scenario merged --delivery-id "unique-delivery-uuid-101"
```
*Expected: Second request returns `status: skipped` ("already completed" or "in progress").*

### 6. Real Historical Public PR Hydration
```bash
python simulate_merge.py --scenario real-pr --repo "fastapi/fastapi" --pr 1000
```

---

## Live GitHub Webhook & ngrok Setup

To receive real webhook events from GitHub repositories:

1. **Start ngrok tunnel**:
   ```bash
   ngrok http 8000
   ```
   Note the forwarding HTTPS URL (e.g., `https://abcdef.ngrok-free.app`).

2. **Configure GitHub Repository Webhook**:
   - In your GitHub repo, go to **Settings** > **Webhooks** > **Add webhook**.
   - **Payload URL**: `https://abcdef.ngrok-free.app/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Enter a secure random string (matching `GITHUB_WEBHOOK_SECRET` in `.env`).
   - **Which events would you like to trigger this webhook?**: Select **"Let me select individual events"** and check **Pull requests**.
   - Click **Add webhook**.

---

## Security, Idempotency, and Failure Handling

- **Credential Redaction**: `SanitizedFormatter` scrubs GitHub tokens (`ghp_*`), Google API keys (`AIza*`), Bearer headers, and SMTP passwords from all logs before writing to `pr_chronicler.log` or console.
- **Idempotency Guarantee**: SQLite with WAL mode tracks `delivery_id` and `(repo, pr_number)` state transitions (`PROCESSING`, `COMPLETED`, `FAILED`, `IGNORED`). Retries of completed PRs do not trigger duplicate LLM calls or duplicate emails.
- **Async Event Loop Offloading**: Blocking SMTP socket I/O runs in worker threads using `asyncio.to_thread` to ensure zero blocking of FastAPI event processing.

---

## Running the Web Application

### 1. Start the FastAPI Backend
```bash
./.venv312/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### 2. Start the Next.js Frontend
```bash
cd frontend
npm run dev -- -p 3000
```
Open your browser at `http://localhost:3000`.

### Navigation & Primary Sections

1. **Explore (`/`)**: Primary GitHub search and discovery experience. Accepts usernames (`tiangolo`), profile URLs (`https://github.com/tiangolo`), or repository URLs (`https://github.com/fastapi/fastapi`). Features recent search history, auto-detection, and quick example chips.
2. **Contributor Profiles (`/profiles` & `/profiles/[username]`)**: Comprehensive public profile metadata, public repositories, and authored pull requests with state filters (`merged`, `open`, `closed`).
3. **Repository Explorer (`/repositories` & `/repositories/[owner]/[repo]`)**: Inspect repository metadata, topics, pull request statuses, and top contributors.
4. **Contributions (`/contributions` & `/contributions/[owner]/[repo]/[prNumber]`)**: Inspect PR changes, file diff patches, and on-demand Gemini AI reflections (Issue Details, Execution Summary, and 3-4 Key Learnings with `[Verified]` vs `[Inferred]` evidence).
5. **AI Learnings (`/learnings`)**: Curated engineering takeaways across all processed pull requests.
6. **Email Outreach (`/outreach`)**: Compose, preview, and dispatch outreach emails referencing specific contributions. Enforces explicit confirmation before sending, generates personalized drafts, and masks recipient email addresses in audit listings.
7. **Webhook Automation (`/webhook-automation`)**: Real-time monitoring of automated merged-PR webhook deliveries.
8. **System Health & Settings (`/system-health`, `/settings`)**: Diagnostics, subsystem readiness, and safe configuration inspection.

