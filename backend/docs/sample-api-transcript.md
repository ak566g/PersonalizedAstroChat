# Sample API transcript

Real output from `python scripts/demo.py` against the server running with `GRAPH_BACKEND=neo4j` and the mock LLM. Regenerate any time with the same command.

### POST /auth/signup

Request:

```json
{
  "email": "rahul+3cb0d7@example.com",
  "password": "correct-horse-battery"
}
```

Response (201):

```json
{
  "session_token": "6LrwCEOSVRWmHrGgVnBIxmrYy0WvlX_UrxHRGRwyp60",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-1",
  "message": "My name is Rahul. I was born on 15 August 1995 in Delhi. I'm planning to switch jobs next year."
}
```

Response (200):

```json
{
  "response": "For your career, focus on sharpening the skills your next role will reward, and make your move when you have a clear plan rather than out of restlessness.",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-1",
  "context_used": [],
  "intent": "career",
  "memory_updates": [
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "name",
      "life_area": null,
      "details": {
        "value": "Rahul"
      }
    },
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "dob",
      "life_area": null,
      "details": {
        "value": "1995-08-15"
      }
    },
    {
      "action": "profile_updated",
      "type": "profile",
      "label": "birth_place",
      "life_area": null,
      "details": {
        "value": "Delhi"
      }
    },
    {
      "action": "created",
      "type": "goal",
      "label": "switch jobs",
      "life_area": "career",
      "details": {}
    }
  ],
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-1",
  "message": "What should I focus on for my career?"
}
```

Response (200):

```json
{
  "response": "Rahul, for your career, focus on sharpening the skills your next role will reward, and make your move when you have a clear plan rather than out of restlessness. Your goal \"switch jobs\" (target 2027) should anchor that plan. As a Leo, you bring confidence, creativity and natural leadership.",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-1",
  "context_used": [
    "career_goal",
    "user_profile",
    "zodiac_sign",
    "recent_conversation"
  ],
  "intent": "career",
  "memory_updates": [],
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-1",
  "message": "Why do you say that?"
}
```

Response (200):

```json
{
  "response": "Rahul, I said that because of what we just discussed: \"Rahul, for your career, focus on sharpening the skills your next role will reward, and make your move when you have a clear plan rather than out of restlessness.\" It follows from the goals and details you've shared with me. As a Leo, you bring confidence, creativity and natural leadership.",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-1",
  "context_used": ["user_profile", "zodiac_sign", "recent_conversation"],
  "intent": "follow_up",
  "memory_updates": [],
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-2",
  "message": "What do you remember about my career goals?"
}
```

Response (200):

```json
{
  "response": "Rahul, here's what I remember about you:\n- [career] Goal: switch jobs (target year 2027)",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-2",
  "context_used": ["career_goal", "user_profile", "zodiac_sign"],
  "intent": "memory_recall",
  "memory_updates": [],
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-2",
  "message": "I'm preparing for a product management interview next month."
}
```

Response (200):

```json
{
  "response": "Rahul, for your career, focus on sharpening the skills your next role will reward, and make your move when you have a clear plan rather than out of restlessness. Your goal \"switch jobs\" (target 2027) should anchor that plan. As a Leo, you bring confidence, creativity and natural leadership.",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-2",
  "context_used": [
    "career_goal",
    "user_profile",
    "zodiac_sign",
    "recent_conversation"
  ],
  "intent": "career",
  "memory_updates": [
    {
      "action": "created",
      "type": "goal",
      "label": "product management interview",
      "life_area": "career",
      "details": {}
    }
  ],
  "degraded": false
}
```

### POST /chat

Request:

```json
{
  "session_id": "session-2",
  "message": "Actually, I don't want to switch jobs anymore \u2014 I want to start my own company instead"
}
```

Response (200):

```json
{
  "response": "Rahul, for your career, focus on sharpening the skills your next role will reward, and make your move when you have a clear plan rather than out of restlessness. Your goal \"product management interview\" (next month) should anchor that plan. As a Leo, you bring confidence, creativity and natural leadership.",
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "session_id": "session-2",
  "context_used": [
    "career_goal",
    "user_profile",
    "zodiac_sign",
    "recent_conversation"
  ],
  "intent": "career",
  "memory_updates": [
    {
      "action": "superseded",
      "type": "goal",
      "label": "start my own company",
      "life_area": "career",
      "details": {
        "replaced": "switch jobs"
      }
    }
  ],
  "degraded": false
}
```

### GET /me

Response (200):

```json
{
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "name": "Rahul",
  "dob": "1995-08-15",
  "time_of_birth": null,
  "birth_place": "Delhi",
  "preferred_language": null,
  "zodiac_sign": "Leo",
  "degraded": false
}
```

### GET /me/brain

Response (200):

```json
{
  "user_id": "0946d3e2-7187-4b73-be54-1bf757968720",
  "facts": [
    {
      "id": "108e6f29-3d98-4955-a1e5-ef00440042fc",
      "type": "goal",
      "label": "switch jobs",
      "status": "superseded",
      "confidence": 0.6,
      "life_area": "career",
      "timeframe": "next year",
      "target_year": 2027,
      "supersedes_id": null,
      "created_at": "2026-10-04T18:46:51.729694+00:00",
      "updated_at": "2026-10-04T18:46:52.270249+00:00"
    },
    {
      "id": "a0998c6c-04c3-48b9-9e5a-21704e31d1fa",
      "type": "goal",
      "label": "product management interview",
      "status": "active",
      "confidence": 0.6,
      "life_area": "career",
      "timeframe": "next month",
      "target_year": null,
      "supersedes_id": null,
      "created_at": "2026-10-04T18:46:52.160201+00:00",
      "updated_at": "2026-10-04T18:46:52.160201+00:00"
    },
    {
      "id": "c1a7d8db-ba79-4b60-8afd-8d1b1c56691e",
      "type": "goal",
      "label": "start my own company",
      "status": "active",
      "confidence": 0.6,
      "life_area": "career",
      "timeframe": null,
      "target_year": null,
      "supersedes_id": "108e6f29-3d98-4955-a1e5-ef00440042fc",
      "created_at": "2026-10-04T18:46:52.270249+00:00",
      "updated_at": "2026-10-04T18:46:52.270249+00:00"
    }
  ],
  "degraded": false
}
```

### GET /health

Response (200):

```json
{
  "status": "ok",
  "graph_backend": "neo4j",
  "llm_provider": "mock"
}
```
