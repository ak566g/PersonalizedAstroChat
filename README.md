# PersonalizedAstroChat — a conversational AI with a "Shared Brain"

A FastAPI service for MyNaksh that answers astrology questions using two kinds of memory:
**short-term** conversation context per session, and a **long-term Shared Brain** (a Neo4j
graph of the user's profile, goals, preferences, interests and life facts) that persists
across sessions. Each message goes through:

```
User message → understand query → select relevant context → build LLM context → generate → update memory
```

It runs fully offline by default (a deterministic mock LLM, so no API key is needed) and can
be switched to Claude with one environment variable. A responsive React web UI is in
[`frontend/`](#web-ui).

```
PersonalizedAstroChat/
├── backend/    FastAPI service, tests, Neo4j docker-compose.yml, scripts, docs
└── frontend/   React + TypeScript web UI (Vite)
```

**Reviewing this submission?** [Quick start](#quick-start) gets it running
in a few minutes with no API key or Docker required. [Key design decisions and
trade-offs](#key-design-decisions-and-trade-offs), [production
considerations](#production-considerations) and [known limitations](#known-limitations) are
the sections most relevant to assessing the engineering judgment behind this; [Tests](#tests)
maps every assignment scenario to the test that covers it, and [Error
handling](#error-handling) covers what was deliberately handled versus left out of scope.

- [Quick start](#quick-start)
- [Web UI](#web-ui)
- [Architecture](#architecture)
- [Shared Brain schema](#shared-brain-schema-neo4j)
- [Memory strategy](#memory-strategy)
- [Context selection](#context-selection)
- [API](#api) and [sample requests/responses](#sample-requests-and-responses)
- [Error handling](#error-handling)
- [Tests](#tests) and [evaluation](#evaluating-whether-the-shared-brain-helps)
- [Design decisions and trade-offs](#key-design-decisions-and-trade-offs)
- [Production considerations](#production-considerations) and [known limitations](#known-limitations)

---

## Quick start

You need Python 3.12+ (developed on 3.14) and, optionally, Docker Desktop for Neo4j. Run
every backend command from the `backend/` folder.

```bash
cd backend

# 1. Neo4j (optional: without it the app falls back to an in-memory graph automatically)
docker compose up -d

# 2. Virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 3. Install and run
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API docs, or run the scripted example
conversation against the running server:

```bash
python scripts/demo.py      # from backend/, with the venv active
```

To use the web UI instead, keep the backend running and see [Web UI](#web-ui).

**Configuration.** Every setting has a working default, so no `.env` file is required. To
change anything, copy `backend/env.example` to `backend/.env`. The main settings:

| Variable                                                   | Default                                                | Meaning                                                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `GRAPH_BACKEND`                                            | `neo4j`                                                | `neo4j` (falls back to in-memory if unreachable) or `memory`                                |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`              | `bolt://localhost:7687` / `neo4j` / `astrochat-dev-pw` | matches `docker-compose.yml`                                                                |
| `LLM_PROVIDER`                                             | `mock`                                                 | `mock` or `anthropic`                                                                       |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT` | –, `claude-opus-5`, `medium`                           | used when `LLM_PROVIDER=anthropic`                                                          |
| `DATA_DIR`                                                 | `./data`                                               | where the SQLite files live, relative to where the server starts (normally `backend/data/`) |
| `CONTEXT_TOP_N` / `SHORT_TERM_TURNS`                       | `5` / `10`                                             | max long-term facts and recent turns sent to the LLM                                        |

**Moving between machines:** transfer the project with `git clone`/`git pull`, not a manual
copy — clipboard and zip transfers have been seen to silently mangle non-ASCII characters (an
em dash in a test fixture became a different whitespace character this way, breaking two
tests in a way that was only visible as a test failure, not a diff). Recreate the virtualenv
on the new machine rather than copying `.venv/` (and `frontend/node_modules/`), and reinstall.
`.gitattributes` normalizes line endings, `.gitignore` keeps virtualenvs, `node_modules/`,
`data/` and `.env` out of git, all paths go through `pathlib`, and the Neo4j data lives in a
named Docker volume, so nothing else needs to change.

---

## Web UI

A React 19 + TypeScript single-page app, built with Vite, in `frontend/`. It needs Node.js 20+.

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, forwards /api/* to the backend on :8000
```

Keep the backend running (`cd backend && uvicorn app.main:app`) in another terminal. To point the UI at a
backend on another address, start it with `VITE_PROXY_TARGET=http://host:port npm run dev`.

**What it does**

- Sign up (birth details optional) and log in; the session token is kept in `localStorage`
  and an expired session returns you to the login screen.
- Chat with suggested starter questions. Each reply shows which context was used ("Career
  goal", "Your profile", "This conversation") and what was saved to the Shared Brain
  ("New goal: switch jobs").
- A conversation list to resume past sessions, and a new-conversation button.
- A **Shared Brain** panel with the profile, sun sign, active goals, interests, preferences
  and life details (with life area, target date and a confidence bar), plus the change
  history of replaced facts. Profile details can be edited in a dialog.
- A status line that switches to "Limited mode" when Neo4j is unreachable, and failed
  messages that can be retried.

**Responsive layout**

| Width               | Layout                                                                                                                                                    |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ≥ 1200px (desktop)  | Three columns: conversations · chat · Shared Brain                                                                                                        |
| 768–1199px (tablet) | Conversations · chat; the Shared Brain opens as a drawer from the brain icon                                                                              |
| < 768px (phone)     | Chat only; conversations and the Shared Brain open as drawers. Inputs use 16px text so iOS doesn't zoom on focus, and the composer respects the safe area |

The UI is keyboard accessible (Enter sends, Shift+Enter adds a line, Escape closes drawers
and dialogs), uses ARIA labels and live regions, and honors `prefers-reduced-motion`.

**Dependencies.** All are open source from the public npm registry; the lockfile contains
no internal-registry URLs. Runtime: `react`, `react-dom` (MIT), `lucide-react` icons (ISC)
and `react-markdown` (MIT). Build and test only: Vite, TypeScript, Vitest, Testing Library
and jsdom (MIT/Apache-2.0). There is no UI component library; styling is plain CSS with
custom properties (`src/styles.css`). The `frontend/.npmrc` keeps registry URLs out of the
lockfile, so `npm install` uses whatever registry your machine is configured for. If that is
a private registry you can't reach, run `npm install --registry=https://registry.npmjs.org/`.

**Other commands:** `npm test` runs the 9 UI tests, `npm run build` typechecks and builds to
`frontend/dist/`, and `npm run preview` serves that build with the same API proxy. To serve
the build from a different origin than the API, set `VITE_API_BASE_URL` at build time and
add the UI origin to the backend's `CORS_ORIGINS` setting (for example
`CORS_ORIGINS='["https://app.example.com"]'`).

---

## Architecture

```
POST /chat {session_id, message}      Authorization: Bearer <session token>
   │
   ├─ auth dependency ─────────────► SQLite auth.db (accounts, sessions)   ← independent of Neo4j
   │       resolves token → user_id (never taken from the request body)
   ▼
ChatService.handle_message(user_id, session_id, message)
   ├─ ShortTermStore.recent(user_id, session_id, k=10) ─► SQLite short_term.db
   ├─ ContextSelector.select(...)
   │     classify: memory_recall > career|relationship|health|finance > follow_up > general
   │     always: profile + sun sign + top-3 preferences + top-3 interests
   │     plus, by category: domain facts | recall facts | nothing (follow-up / general)
   ├─ LLMProvider.generate(system prompt + recent turns + message)
   │     MockProvider (default) | AnthropicProvider
   ├─ ShortTermStore.append(user turn, assistant turn)
   └─ MemoryExtractor.extract(message)  (best effort: a failure never fails the request)
         profile cues → ProfileService.update   (in-place overwrite)
         facts / corrections → GraphRepository.upsert_facts
                                     │
                     ResilientGraphRepository ─► Neo4jGraphRepository
                                     └─(Neo4j unreachable)─► shared InMemoryGraphRepository
```

Backend modules (under `backend/`):

| Module                      | Responsibility                                                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------------- |
| `app/api/`                  | FastAPI routes, request/response schemas, auth dependency                                      |
| `app/auth/`, `app/storage/` | signup/login/logout, PBKDF2 password hashing, SQLite account and session store                 |
| `app/chat/`                 | orchestration (`service.py`) and system-prompt building (`prompt.py`)                          |
| `app/memory/`               | short-term store, context selector, memory extractor, shared life-area classifier              |
| `app/brain/`                | graph models, the `GraphRepository` protocol, Neo4j and in-memory backends, resilience wrapper |
| `app/llm/`                  | `LLMProvider` protocol, mock and Anthropic providers, factory                                  |
| `app/profile/`              | profile service and stub sun-sign calculation                                                  |

All route handlers are plain `def` functions, so FastAPI runs them in its threadpool. The
blocking calls (SQLite, the Neo4j driver, the Anthropic SDK) therefore never block the event
loop, without async plumbing in every layer.

---

## Shared Brain schema (Neo4j)

```
(:User {user_id, name, dob, time_of_birth, birth_place, preferred_language, zodiac_sign})
   ├─[:HAS_GOAL]──────►(:Goal       {id, label, status, confidence, timeframe, target_year, created_at, updated_at})─[:RELATES_TO]─►(:LifeArea {name})
   ├─[:HAS_MEMORY]────►(:Memory     {id, label, status, confidence, ...})──────────────────────────────────────────[:RELATES_TO]─►(:LifeArea)
   ├─[:PREFERS]───────►(:Preference {id, label, status, confidence, ...})
   └─[:INTERESTED_IN]─►(:Interest   {id, label, status, confidence, ...})

(new fact)-[:SUPERSEDES]->(old fact)          correction history, for any fact type
LifeArea nodes: career, relationship, health, finance
```

**Entities.** The user profile and astrology attributes are properties on `User`. Goals,
preferences, interests and free-form memories ("I work as a software engineer at Infosys")
are their own nodes, so each one has its own confidence, status and timestamps. `LifeArea`
nodes are shared across users and categorize goals and memories.

**Relationships.** One ownership relationship per fact type, `RELATES_TO` for categorization,
and `SUPERSEDES` to keep a correction trail ("start my own company" supersedes "switch jobs").

**Constraints.** Created idempotently at startup: uniqueness on `User.user_id`, on `id` for
each fact label and on `LifeArea.name`. These also act as the indexes every lookup uses.

**Retrieval.** There are four bounded query shapes, never a full-graph dump:

1. **Always included:** the profile, plus the top 3 active preferences and the top 3 active interests.
2. **Life-area question** ("What should I focus on for my career?"):
   `(u)-[:HAS_GOAL|HAS_MEMORY]->(f)-[:RELATES_TO]->(:LifeArea {name: $area})`. The life-area hop
   is a required `MATCH`, not an `OPTIONAL MATCH`, so facts from other areas are actually excluded.
   Results are ordered by confidence, then recency, limited to `CONTEXT_TOP_N`.
3. **Recall** ("What do you remember about my career goals?"): facts in the mentioned area
   first, then other active facts, up to `CONTEXT_TOP_N`.
4. **Follow-up or general question:** no fact query.

**Why Neo4j.** The data is a graph: a user linked to typed facts, linked to shared life
areas, with correction chains between facts. "This user's active career facts, ranked" is a
single pattern match in Cypher. The `GraphRepository` protocol keeps the storage layer
replaceable. The in-memory backend implements the same protocol, and both backends share one
implementation of the update policy (`FactWriteMixin`), so their behavior cannot drift apart.
`test_repository_contract.py` runs the same tests against both.

---

## Memory strategy

**What is remembered.** Each clause of the user's message (split on sentence punctuation and
dashes) is checked in this order:

1. **Profile cues:** name, date of birth, birth time, birth place, preferred language →
   overwritten in place on the `User` node. There is no history for these; only the current
   value matters. "Actually I was born in 1996, not 1995" changes only the year.
2. **Negations:** "I don't want to switch jobs anymore", "I'm no longer interested in …" →
   retract the matching active fact. If the same message states a replacement ("— I want to
   start my own company instead"), the new fact supersedes the old one.
3. **Facts:** goals ("planning to …", "preparing for …", "my goal is …"), preferences
   ("I prefer …"), interests ("I'm interested in …", "I love …") and life facts ("I work …",
   "I have two kids", "my wife is …").

Processing each clause separately is what lets the spec's first message produce a name, a
date of birth, a birth place _and_ a career goal in one turn.

**What is not remembered.** Questions, small talk, requests ("I want to know what my
horoscope says") and the assistant's own replies. A statement before a trailing question is
still kept: "I'm planning to switch jobs next year, what do you think?" stores the goal.

**How memories are represented.** Each fact has a label, a type, a status
(`active` / `superseded` / `retracted`), a confidence score, timestamps and, for goals and
life facts, a life area. Time expressions are parsed: "next year" becomes
`target_year = current year + 1` (2027, as in the spec example) and "next month" is kept as
`timeframe`.

**How existing memories are updated.**

| Situation                                   | Effect                                                                                               |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| New fact                                    | Created with confidence 0.6 and tagged with a life area                                              |
| Same fact restated (token similarity ≥ 0.5) | Reinforced: confidence + 0.15, capped at 1.0, and the timeframe is updated if a new one is given     |
| Correction with a replacement               | Old fact marked `superseded`; new fact created with a `SUPERSEDES` link and the old fact's life area |
| Correction without a replacement            | Fact marked `retracted`                                                                              |
| Correction that matches no fact             | Dropped. A stated replacement is still stored as a new fact                                          |

Life areas are assigned when a fact is written, using the same keyword classifier the read
path uses (`memory/life_area_classifier.py`). The classifier runs on the whole clause, not
just the extracted label, so "switch jobs" is tagged `career` because the clause contains "jobs".

---

## Context selection

Each message gets exactly one category, checked in this order:

1. **`memory_recall`**: "remember", "told you", "what do you know about me". Checked first
   because "what do you remember about my _career_ goals" also contains a life-area word.
2. **A life area** (career, relationship, health, finance), by keyword. Checked before
   follow-up, so "Why is my career going downhill?" is a career question.
3. **`follow_up`**: a short message such as "why", "tell me more" or "that", sent when the
   session already has history. Answered from recent turns only, with no fact query.
4. **`general_astrology`**: profile and sign only.

The LLM receives the system prompt (instructions, profile and sun sign, the selected facts,
preferences and interests, and the preferred language), the last `SHORT_TERM_TURNS` turns of
_this user's_ session, and the message. `context_used` in the response lists what was
included, for example `["career_goal", "user_profile", "zodiac_sign", "recent_conversation"]`.

---

## API

| Method & path                            | Auth   | Purpose                                                                                                                    |
| ---------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------- |
| `POST /auth/signup`                      | –      | `{email, password, name?, dob?, time_of_birth?, birth_place?, preferred_language?}` → `{session_token, user_id, degraded}` |
| `POST /auth/login`                       | –      | `{email, password}` → `{session_token}`; each login is an independent session                                              |
| `POST /auth/logout`                      | Bearer | revokes only the token used for the call                                                                                   |
| `GET /me` / `PATCH /me`                  | Bearer | read or update your own profile; the sun sign is recomputed when the date of birth changes                                 |
| `GET /me/brain`                          | Bearer | debug view of every stored fact (including superseded ones)                                                                |
| `GET /me/sessions`                       | Bearer | your conversations, most recent first, titled by their first message                                                       |
| `GET /me/sessions/{session_id}/messages` | Bearer | the stored turns of one of your conversations                                                                              |
| `POST /chat`                             | Bearer | `{session_id, message}` → `{response, user_id, session_id, context_used, intent, memory_updates, degraded}`                |
| `GET /health`                            | –      | `{status, graph_backend, llm_provider}`                                                                                    |

**One deliberate deviation from the spec.** The spec's example `/chat` request includes
`user_id`. Here `user_id` is derived from the session token and any `user_id` in the request
body is ignored. Trusting a client-supplied `user_id` would let any logged-in user read or
write someone else's Shared Brain by editing one field. The response still returns `user_id`,
as in the spec. The response format is extended with `intent`, `memory_updates` and
`degraded`, which the spec allows.

### Sample requests and responses

Captured from the server running against Neo4j with the mock LLM. The full transcript (eight
calls) is in [`backend/docs/sample-api-transcript.md`](backend/docs/sample-api-transcript.md).

```bash
curl -s -X POST localhost:8000/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"rahul@example.com","password":"correct-horse-battery"}'
# {"session_token":"YMTTNw4x…","user_id":"81672761-…","degraded":false}
TOKEN=YMTTNw4x…
```

**1 · First message: profile and goal extracted**

```bash
curl -s -X POST localhost:8000/chat -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"session_id":"session-1","message":"My name is Rahul. I was born on 15 August 1995 in Delhi. I'"'"'m planning to switch jobs next year."}'
```

```json
{
  "response": "For your career, focus on sharpening the skills your next role will reward, ...",
  "context_used": [],
  "intent": "career",
  "memory_updates": [
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "name",
      "details": { "value": "Rahul" }
    },
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "dob",
      "details": { "value": "1995-08-15" }
    },
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "birth_place",
      "details": { "value": "Delhi" }
    },
    {
      "action": "created",
      "type": "goal",
      "label": "switch jobs",
      "life_area": "career"
    }
  ],
  "degraded": false
}
```

**2 · "What should I focus on for my career?": personalized from the Shared Brain**

```json
{
  "response": "Rahul, for your career, focus on sharpening the skills your next role will reward, ... Your goal \"switch jobs\" (target 2027) should anchor that plan. As a Leo, you bring confidence, creativity and natural leadership.",
  "context_used": [
    "career_goal",
    "user_profile",
    "zodiac_sign",
    "recent_conversation"
  ],
  "intent": "career"
}
```

**3 · "Why do you say that?": answered from short-term context, no graph facts**

```json
{
  "response": "Rahul, I said that because of what we just discussed: \"Rahul, for your career, focus on ...\"",
  "context_used": ["user_profile", "zodiac_sign", "recent_conversation"],
  "intent": "follow_up"
}
```

**4 · New session, "What do you remember about my career goals?"**

```json
{
  "response": "Rahul, here's what I remember about you:\n- [career] Goal: switch jobs (target year 2027)",
  "session_id": "session-2",
  "context_used": ["career_goal", "user_profile", "zodiac_sign"],
  "intent": "memory_recall"
}
```

**5 · Correction: "Actually, I don't want to switch jobs anymore — I want to start my own company instead"** → `GET /me/brain`

```json
{
  "facts": [
    {
      "label": "switch jobs",
      "status": "superseded",
      "life_area": "career",
      "target_year": 2027
    },
    {
      "label": "product management interview",
      "status": "active",
      "life_area": "career",
      "timeframe": "next month"
    },
    {
      "label": "start my own company",
      "status": "active",
      "life_area": "career",
      "supersedes_id": "<id of 'switch jobs'>"
    }
  ]
}
```

---

## Error handling

| Failure                                                                                           | Behavior                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Invalid input (blank or too-long message, bad `session_id`, short password, future DOB, bad time) | `422` with field-level details                                                                                                                                                                                                             |
| Missing, invalid or revoked token                                                                 | `401` with `WWW-Authenticate: Bearer`. There is no `403` case: no endpoint takes a `user_id` a caller could get wrong                                                                                                                      |
| Duplicate email                                                                                   | `409`, enforced by a UNIQUE constraint so concurrent signups can't both succeed                                                                                                                                                            |
| Wrong password or unknown email                                                                   | Identical `401` responses (unknown emails are hashed too, so timing doesn't reveal which emails exist)                                                                                                                                     |
| **LLM failure** (timeout, API error, refusal, empty reply)                                        | `200` with a short apology that uses the user's name, `degraded: true`; memory is still updated                                                                                                                                            |
| **Neo4j down** at startup or mid-session                                                          | Calls go to one shared in-memory graph; `200` with `degraded: true` on every graph-backed endpoint, `/health` reports `in_memory`. Neo4j is retried at most every 10s; the first successful call re-runs schema setup and LifeArea seeding |
| Neo4j down, but the session token is valid                                                        | Login and auth keep working, because accounts and sessions are in SQLite, not the graph                                                                                                                                                    |
| Missing profile fields                                                                            | Chat works; the sun sign is omitted and the prompt asks the model to invite details                                                                                                                                                        |
| Empty memory or no relevant context                                                               | Normal answer from profile and conversation; recall says nothing is saved yet                                                                                                                                                              |
| Memory-extraction bug                                                                             | Logged; the reply is still returned (memory updates are best effort)                                                                                                                                                                       |
| Signup fails after the account row is written                                                     | The account row is rolled back, so a retry doesn't get a false `409`                                                                                                                                                                       |
| Anything unexpected                                                                               | `500 {"detail": "Internal server error"}`, logged with a stack trace                                                                                                                                                                       |

These were verified against a real Neo4j by stopping the container mid-session: chat
returned `200`/`degraded: true`, `/health` reported `in_memory`, and after the restart it
reported `neo4j` and recalled the goal stored before the outage. The first request after
Neo4j goes down takes about 7 seconds to detect the failure (connection timeout plus driver
retry). Requests after that skip Neo4j until the retry interval passes.

---

## Tests

```bash
cd backend
pytest                                # 87 tests, no Docker needed (in-memory graph, mock LLM)
RUN_INTEGRATION=1 pytest              # + 5 repository-contract tests against real Neo4j (docker compose up -d first)

cd ../frontend
npm test                              # 9 UI tests (login, signup, chat, retry, history, limited mode, logout)
```

92 backend tests exist: 87 run with just `pytest` (all pass), plus 5 Neo4j
repository-contract tests that run only under `RUN_INTEGRATION=1` (also all pass, verified
against a real container). All 9 UI tests pass. The scenario tests are named after the plan's
scenario numbers:

| #   | Scenario                                          | Test                                                                                |
| --- | ------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 1   | New user                                          | `test_chat_flow::test_01_new_user_first_chat_has_minimal_context`                   |
| 2   | Creating a long-term memory                       | `test_chat_flow::test_02_goal_statement_becomes_long_term_memory`                   |
| 3   | Retrieving a memory                               | `test_chat_flow::test_03_memory_recall_retrieves_stored_goal_in_new_session`        |
| 4   | Follow-up question                                | `test_chat_flow::test_04_follow_up_uses_short_term_context_not_the_graph`           |
| 5   | New session using previous information            | `test_chat_flow::test_05_new_session_still_personalizes_from_shared_brain`          |
| 6   | Irrelevant memory excluded                        | `test_chat_flow::test_06_irrelevant_memory_is_excluded`                             |
| 7   | User corrects a goal (supersede chain)            | `test_memory_extraction::test_07_correcting_a_goal_supersedes_it`                   |
| 8   | User corrects a profile field                     | `test_profile::test_08_profile_correction_in_chat_overwrites_in_place`              |
| 9   | Missing user information                          | `test_chat_flow::test_09_missing_profile_information_still_answers`                 |
| 10  | LLM failure                                       | `test_error_handling::test_10_llm_failure_returns_fallback_reply`                   |
| 11  | Graph failure mid-session, then recovery          | `test_error_handling::test_11_graph_outage_mid_session_degrades_instead_of_failing` |
| 12  | Nothing stored for questions or small talk        | `test_memory_extraction::test_12_*`                                                 |
| 13  | Auth: 401s, 409, login, logout, multiple sessions | `test_auth::test_13a`–`test_13g`                                                    |
| 14  | Two users' Shared Brains stay separate            | `test_chat_flow::test_14_two_users_never_see_each_others_long_term_memory`          |
| 15  | Auth keeps working during a Neo4j outage          | `test_auth::test_15_auth_survives_a_graph_outage`                                   |
| 16  | Same `session_id` from two users stays separate   | `test_chat_flow::test_16_same_session_id_from_two_users_keeps_histories_separate`   |

`test_chat_flow::test_spec_example_conversation_end_to_end` replays the assignment's example
conversation. The remaining tests cover the extractor rules, classification order,
reinforcement and confidence caps, sun-sign boundaries, input validation and the
resilience wrapper (one shared fallback instance, retry interval, re-seeding on recovery).

---

## Evaluating whether the Shared Brain helps

There is no evaluation framework in this submission. With a real LLM, I would measure each
property with a small hand-labelled conversation set (about 30 to 50 scripted
conversations, each with expected facts and expected `context_used`):

| Property                     | Measurement                                                                                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Memory accuracy**          | Precision and recall of `memory_updates` against hand-labelled facts per message. Precision matters more: a wrong memory hurts more than a missed one                        |
| **Context relevance**        | For each message, is the expected fact in `context_used` (recall), and is everything in it relevant (precision)? The scenario tests are the deterministic core of this check |
| **Personalization**          | A/B: the same question with and without Shared Brain context, rated pairwise by an LLM judge or by people ("Does this answer use what the user told us?")                    |
| **Conversation consistency** | After a correction (scenario 7), later answers in the same and in new sessions must use the new fact and never the superseded one                                            |
| **Irrelevant context**       | Rate of facts in `context_used` from a different life area than the question; should be about 0 with the required life-area match                                            |
| **Memory persistence**       | Facts recalled in a new session and after a restart. The contract tests check this against real Neo4j                                                                        |

In production I would also track how often `memory_updates` is non-empty, the correction
rate (users re-stating facts suggests the extractor missed something), the `degraded` rate,
and thumbs-up/down on answers that used Shared Brain context compared with answers that didn't.

---

## Key design decisions and trade-offs

- **Rule-based extraction and classification, not LLM-based.** Deterministic, free, fast and
  fully testable offline. The cost is recall: unusual phrasings are missed. The extractor
  sits behind one function (`MemoryExtractor.extract`), so an LLM-based extractor with
  structured outputs could replace it, or run as a second pass, without touching the rest.
- **Mock LLM by default.** The whole pipeline, including personalization, can be shown and
  tested without an API key. With `LLM_PROVIDER=anthropic` it uses `claude-opus-5` at
  `medium` effort, with server-side refusal fallbacks enabled
  (`server-side-fallback-2026-07-01`), so a safety decline is retried on a fallback model
  instead of failing.
- **Neo4j with an in-memory fallback** behind one protocol, plus a short circuit breaker.
  The service stays available during an outage, at the cost of facts written during the
  outage not being copied back to Neo4j (see limitations).
- **SQLite for short-term memory and auth** instead of Redis or Postgres. No extra
  infrastructure, and data survives restarts. Auth is deliberately _not_ in Neo4j, so a
  graph outage never locks users out.
- **Email/password with opaque session tokens** rather than JWTs. Logout is instant
  revocation, which is simpler than token denylists. Passwords use stdlib PBKDF2-SHA256 with
  310,000 iterations (the OWASP baseline), which avoids an extra dependency; argon2id is the
  production upgrade.
- **Lexical similarity for matching restated facts** (token Jaccard ≥ 0.5). Simple and
  explainable; embeddings would catch paraphrases such as "change careers" vs "switch jobs".
- **One deterministic category per message.** Easy to test and reason about; a message
  spanning two life areas only gets the dominant one.

## Production considerations

Deliberately not built, in rough priority order:

- **Security:** rate limiting (especially on `/auth/login`), token expiry and refresh, email
  verification and password reset, argon2id hashing, HTTPS-only deployment, secrets from a
  secret manager.
- **Data:** Postgres instead of SQLite for multi-instance deployments; Neo4j backups;
  copying facts written during an outage back to Neo4j (for example a write-ahead outbox);
  data export and deletion (DPDP/GDPR); retention limits on chat history.
- **Quality:** LLM-based extraction with confidence thresholds; embeddings for fact matching
  and retrieval; memory decay for stale goals; conversation summarization for long sessions;
  multilingual extraction (rules are English-only today; replies follow `preferred_language`
  when a real LLM is used).
- **Operations:** structured logs and tracing per request, metrics (latency, `degraded`
  rate, LLM cost per conversation), CI running both test tiers, container images and k8s
  deployment, and an async Neo4j driver if request concurrency grows.

## Known limitations

- **A signup that happens entirely during a Neo4j outage can lose that user's profile.** The
  account (in SQLite) survives, but the profile only exists in the in-memory fallback until
  the process restarts and is never copied to Neo4j. The signup response reports
  `degraded: true`, and `PATCH /me` recreates the profile node, but nothing recovers it
  automatically. Facts written by existing users during an outage are also not copied back.
- Profile details stated in free text are only captured when they match a known cue ("my
  name is", "born on/in/at", "talk to me in …"); otherwise use signup or `PATCH /me`.
- Fact matching is lexical, so paraphrased restatements of a free-form memory can create
  near-duplicates.
- Sessions don't expire; there is no email verification, password reset or login throttling.
- The mock LLM returns templated text and doesn't translate into `preferred_language`.
- Astrology is a stub: the sun sign is computed from the date of birth only.
