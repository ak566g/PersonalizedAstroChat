from app.tests.conftest import DEFAULT_PASSWORD, chat, signup


def _login(client, email, password=DEFAULT_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_13a_missing_token_is_401(client):
    assert (
        client.post("/chat", json={"session_id": "s", "message": "hi"}).status_code
        == 401
    )
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_13b_unknown_token_is_401(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/me", headers=headers).status_code == 401


def test_13c_duplicate_email_is_409_case_insensitively(client):
    signup(client, "dup@example.com")
    response = client.post(
        "/auth/signup",
        json={"email": "DUP@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 409


def test_13d_wrong_password_and_unknown_email_look_identical(client):
    signup(client, "user@example.com")
    wrong_password = _login(client, "user@example.com", "nope-nope-nope")
    unknown_email = _login(client, "ghost@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_13e_logout_revokes_that_token(client):
    headers, _ = signup(client, "bye@example.com")
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).status_code == 401


def test_13f_login_returns_a_working_token(client):
    signup(client, "login@example.com", name="Lia")
    response = _login(client, "login@example.com")
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['session_token']}"}
    assert chat(client, headers, "Hello")["response"]
    assert client.get("/me", headers=headers).json()["name"] == "Lia"


def test_13g_logout_revokes_only_one_of_several_sessions(client):
    signup(client, "multi@example.com")
    phone = {
        "Authorization": f"Bearer {_login(client, 'multi@example.com').json()['session_token']}"
    }
    web = {
        "Authorization": f"Bearer {_login(client, 'multi@example.com').json()['session_token']}"
    }
    client.post("/auth/logout", headers=phone)
    assert client.get("/me", headers=phone).status_code == 401
    assert client.get("/me", headers=web).status_code == 200


def test_user_id_in_chat_body_is_ignored(client):
    alice, alice_id = signup(client, "alice@example.com")
    _, bob_id = signup(client, "bob@example.com")
    response = client.post(
        "/chat",
        json={
            "user_id": bob_id,
            "session_id": "s",
            "message": "I'm planning to move abroad next year.",
        },
        headers=alice,
    )
    assert response.json()["user_id"] == alice_id
    assert client.container.graph.call("list_facts", bob_id)[0] == []


def test_15_auth_survives_a_graph_outage(client, graph):
    headers, _ = signup(client, "outage@example.com", name="Ravi")
    graph.down = True
    body = chat(client, headers, "What should I focus on for my career?")
    assert body["degraded"] is True
    login = _login(client, "outage@example.com")
    assert login.status_code == 200