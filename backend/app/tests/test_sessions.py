from app.tests.conftest import chat, signup


def test_sessions_are_listed_most_recent_first_with_titles(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.", session_id="older")
    chat(client, headers, "How is my health looking?", session_id="newer")
    chat(client, headers, "Tell me more", session_id="newer")
    sessions = client.get("/me/sessions", headers=headers).json()["sessions"]
    assert [(s["session_id"], s["title"], s["message_count"]) for s in sessions] == [
        ("newer", "How is my health looking?", 4),
        ("older", "I'm planning to switch jobs next year.", 2),
    ]


def test_session_history_returns_turns_in_order(client, rahul):
    headers, _ = rahul
    chat(client, headers, "Hello", session_id="s1")
    chat(client, headers, "Tell me about Leo", session_id="s1")
    messages = client.get("/me/sessions/s1/messages", headers=headers).json()[
        "messages"
    ]
    assert [(m["role"], m["content"]) for m in messages][::2] == [
        ("user", "Hello"),
        ("user", "Tell me about Leo"),
    ]
    assert all(m["role"] == "assistant" for m in messages[1::2])


def test_sessions_are_private_to_their_owner(client):
    alice, _ = signup(client, "alice@example.com")
    bob, _ = signup(client, "bob@example.com")
    chat(client, alice, "I'm planning to move abroad next year.", session_id="shared")
    assert client.get("/me/sessions", headers=bob).json()["sessions"] == []
    assert (
        client.get("/me/sessions/shared/messages", headers=bob).json()["messages"] == []
    )
    assert client.get("/me/sessions", headers={}).status_code == 401


def test_invalid_session_id_in_path_is_422(client, rahul):
    headers, _ = rahul
    assert (
        client.get("/me/sessions/bad%20id/messages", headers=headers).status_code == 422
    )