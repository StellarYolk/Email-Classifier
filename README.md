# Email Classifier


A local, agentic CLI tool that classifies your unread Gmail inbox using a locally-run LLM (via Ollama), sorts emails into Gmail labels automatically, and hands off anything it can't confidently place to the user for a quick interactive decision.

Built as a learning project for understanding agentic systems from scratch - no agent framework is used; the classify $\rightarrow$ validate $\rightarrow$ act $\rightarrow$ record loop is hand-rolled in plain Python.


## What it does (In this version)

- Fetches unread inbox (`in:inbox is:unread`), 20 emails at a time
- Hard-coded a set of labels into the categories **Sorted**, **Archived**, and **Held**. Each label has it's own description in the system prompt for classification
- Classifies each email using a local LLM (Ollama), more specifically Llama3.2:3b model, constrained to a strict JSON schema via Pydantic
- Automatically applies Gmail labels and takes action based on the result:
  - **Sorted** labels stay in the inbox 
  - **Archived** labels are applied *and* removed from the inbox (spam, food delivery)
  - **Held** labels (`delete`, `unknown`) are queued and reviewed with you interactively after each batch - you choose a real label, send it to Trash, or leave it untouched
- Tracks progress in a cursor file so an interrupted run can resume without reprocessing or losing anything
- Writes a human-readable report of every decision made with the reasoning for each classification written clearly so that debugging is easier


## Architecture

| File | Responsibility |
|---|---|
| `schema.py` | The `Label` enum and `EmailClassification` Pydantic model - the strict contract every LLM response must satisfy. Also defines which labels are auto-sorted, auto-archived, or held. |
| `classify.py` | Calls Ollama with a schema-constrained prompt, validates the response, and retries with corrective feedback on failure (falling back to `unknown` after repeated failures). |
| `html_utils.py` | Strips HTML emails down to clean, token-efficient plain text when no plain-text part is available. |
| `gmail_auth.py` | OAuth login + token caching. |
| `gmail_client.py` | Fetches unread message IDs, pulls full message content, and parses Gmail's MIME payload tree into a plain `{id, sender, subject, body}` dict. |
| `gmail_actions.py` | Applies real outcomes in Gmail: creates/reuses labels (namespaced under `Classifier/` to avoid colliding with Gmail's reserved system labels), archives, and trashes. |
| `persistence.py` | The cursor file (`processed_ids.txt`) and the per-run report file (`report_YYYY-MM-DD_HHMM.txt`), both written to incrementally, per email, as each outcome becomes final. |
| `main.py` | The batch loop, routing logic, and interactive held-email review. Entry point. |


## How a run works

1. Fetches up to 20 unread emails (via Gmail's own pagination)
2. Classifies and routes each one; sorted/archived outcomes are applied to Gmail and recorded immediately
3. Any held emails (`delete` / `unknown`) are reviewed together, after the rest of the batch - you're shown the model's guess and reasoning, and choose a real label, Trash, or leave it alone
4. Prints a summary (`Sorted: X  Archived: Y  Held: Z`) and asks permission before fetching the next batch
5. If interrupted at any point, rerunning will skip everything already recorded in `processed_ids.txt` and continue from where it left off

## Setup

**1. Install dependencies**
```
pip install pydantic requests beautifulsoup4 google-auth-oauthlib google-api-python-client
```

**2. Install Ollama and pull the model**
```
ollama pull llama3.2:3b
```

Ollama must be running locally (`http://localhost:11434`) before you run the classifier.

**3. Set up Gmail API access**

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Gmail API** (APIs & Services $\rightarrow$ Library)
3. Configure the **OAuth consent screen**:
   - Add yourself under **Test users** (required - the app stays in "Testing" mode, which is fine for personal/single-user use, but Google will reject login from any account not explicitly added here)
4. Create credentials: **APIs & Services $\rightarrow$ Credentials $\rightarrow$ Create Credentials $\rightarrow$ OAuth Client ID**, application type **Desktop app**
5. Download the resulting `credentials.json` and place it in this project's root folder

On first run, a browser window will open asking you to log in and approve access. A `token.json` is then cached locally so this doesn't happen again on every run


## Usage

```
python3 main.py
```

This runs against your real inbox via `run_from_gmail()`.

A fake-email test harness is also available at the bottom of `main.py` (commented out) for exercising the batching/routing/persistence logic without touching Ollama or Gmail at all - useful when working on pipeline logic in isolation.

## Label categories

| Label | Bucket | Behavior |
|---|---|---|
| `job_postings` | Sorted | Labeled, stays in inbox |
| `coding_contests` | Sorted | Labeled, stays in inbox |
| `hackathons` | Sorted | Labeled, stays in inbox |
| `newsletter` | Sorted | Labeled, stays in inbox |
| `security` | Sorted | Labeled, stays in inbox |
| `spam` | Archived | Labeled, removed from inbox |
| `food_delivery` | Archived | Labeled, removed from inbox |
| `delete` | Held | You confirm before it's trashed |
| `unknown` | Held | You pick a label, trash it, or leave it as-is |

All custom Gmail labels are created under a `Classifier/` prefix (e.g. `Classifier/Job Postings`) to avoid colliding with Gmail's own reserved system label names (`Spam`, `Inbox`, etc. are not creatable as custom labels).


## Known limitations of the current version 

- **No memory / learning loop** - the model doesn't yet adapt based on your corrections. Deferred to a future version.
- **No date-range selection** - always processes current unread mail.
- **No Docker packaging** - runs as a plain local script for now.
- **No confidence thresholds** - the model always commits to one of the 9 labels (or falls back to `unknown` on repeated validation failure); there's no "I'm not sure enough, ask the user anyway" middle ground yet.


## Plans for the future

- Add a learning loop so that the model learns from it's own classification
- Process emails as it comes in the inbox and send appropriate notification to the user with the rated urgency
- Package this in a docker container (for easier deployment)
- Run this as a background application or host this on a VPS (Still decising on this part)


## Notes on model behavior

`llama3.2:3b` running locally is capable but not infallible - on content with little genuine classification signal (e.g. generic test strings), its output can land inconsistently between plausible labels like `spam` and `unknown`. This is expected behavior near a model's decision boundary and not a bug in the classification pipeline; real emails with real signal (verification codes, contest invites, order confirmations, etc.) classify far more reliably.