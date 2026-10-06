"""Walk through the assignment's example conversation against a running server.

python scripts/demo.py [base_url]
(default http://localhost:8000)
"""
import json
import sys
import uuid
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def show(
    method: str, path: str, response: httpx.Response, body: dict | None = None
) -> None:
    print(f"\n### {method} {path}")
    if body is not None:
        print("Request:\n```json\n" + json.dumps(body, indent=2) + "\n```\n")
    text = (
        json.dumps(response.json(), indent=2)
        if response.content
        else "(no content)"
    )
    print(f"Response ({response.status_code}):\n```json\n{text}\n```\n")


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=60)
    email = f"rahul+{uuid.uuid4().hex[:6]}@example.com"
    signup_body = {"email": email, "password": "correct-horse-battery"}
    r = client.post("/auth/signup", json=signup_body)
    show("POST", "/auth/signup", r, signup_body)
    client.headers["Authorization"] = f"Bearer {r.json()['session_token']}"

    conversation = [
        (
            "session-1",
            "My name is Rahul. I was born on 15 August 1995 in Delhi. I'm planning to switch jobs next year.",
        ),
        ("session-1", "What should I focus on for my career?"),
        ("session-1", "Why do you say that?"),
        ("session-2", "What do you remember about my career goals?"),
        ("session-2", "I'm preparing for a product management interview next month."),
        (
            "session-2",
            "Actually, I don't want to switch jobs anymore — I want to start my own company instead",
        ),
    ]

    for session_id, message in conversation:
        body = {"session_id": session_id, "message": message}
        show("POST", "/chat", client.post("/chat", json=body), body)

    show("GET", "/me", client.get("/me"))
    show("GET", "/me/brain", client.get("/me/brain"))
    show("GET", "/health", client.get("/health"))


if __name__ == "__main__":
    main()