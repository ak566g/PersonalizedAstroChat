import pytest
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.models import CandidateFact, FactType
from app.brain.resilient_repository import ResilientGraphRepository
from app.tests.conftest import FlakyGraph, brain, chat, signup


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "s1", "message": ""},
        {"session_id": "s1", "message": "   "},
        {"session_id": "", "message": "hi"},
        {"session_id": "bad id with spaces", "message": "hi"},
        {"message": "hi"},
        {"session_id": "s1", "message": "x" * 4001},
    ],
)
def test_invalid_chat_input_is_422(client, rahul, payload):
    headers, _ = rahul
    assert client.post("/chat", json=payload, headers=headers).status_code == 422


def test_short_password_is_422(client):
    response = client.post(
        "/auth/signup", json={"email": "a@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_10_llm_failure_returns_fallback_reply(client, rahul, llm):
    headers, _ = rahul
    llm.fail = True
    body = chat(client, headers, "I'm planning to switch jobs next year.")
    assert body["degraded"] is True
    assert (
        "can't reach my guidance engine" in body["response"]
        and "Rahul" in body["response"]
    )
    # Memory is still updated even though the LLM failed.
    assert [u["action"] for u in body["memory_updates"]] == ["created"]


def test_11_graph_outage_mid_session_degrades_instead_of_failing(client, rahul, graph):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.")
    graph.down = True
    body = chat(client, headers, "What should I focus on for my career?")
    assert body["degraded"] is True
    assert body["response"]
    assert client.get("/health").json()["status"] == "degraded"
    assert client.get("/me", headers=headers).json()["degraded"] is True
    graph.down = False
    assert (
        chat(client, headers, "What should I focus on for my career?")["degraded"]
        is False
    )
    assert client.get("/health").json() == {
        "status": "ok",
        "graph_backend": "neo4j",
        "llm_provider": "mock",
    }


def test_signup_during_outage_is_flagged_degraded(client, graph):
    graph.down = True
    response = client.post(
        "/auth/signup",
        json={"email": "late@example.com", "password": "long-enough-pw"},
    )
    assert response.status_code == 201
    assert response.json()["degraded"] is True


def test_memory_update_bug_does_not_fail_the_request(client, rahul, monkeypatch):
    headers, _ = rahul

    def boom(*_args, **kwargs):
        raise RuntimeError("bug in extractor")

    monkeypatch.setattr(client.container.chat._extractor, "extract", boom)
    body = chat(client, headers, "I'm planning to switch jobs next year.")
    assert body["response"] and body["memory_updates"] == []


def test_empty_memory_and_no_relevant_context(client, rahul):
    headers, _ = rahul
    assert brain(client, headers) == []
    recall = chat(client, headers, "What do you remember about me?")
    assert "don't have anything saved" in recall["response"]


def test_fallback_state_is_shared_and_recovery_reseeds_primary():
    primary = FlakyGraph()
    clock = [0.0]
    resilient = ResilientGraphRepository(
        primary,
        InMemoryGraphRepository(),
        retry_interval=10,
        clock=lambda: clock[0],
    )
    primary.down = True
    resilient.initialize()
    assert resilient.backend_name == "in_memory"
    view = resilient.scoped()
    view.upsert_facts("u1", [CandidateFact(FactType.GOAL, "learn guitar")])
    assert view.degraded is True
    assert [f.label for f in resilient.scoped().list_facts("u1")] == ["learn guitar"]  # same fallback instance
    primary.down = False
    calls_before = len(primary.calls)
    resilient.scoped().ping()  # within retry interval: primary not probed
    assert len(primary.calls) == calls_before
    clock[0] = 11
    assert resilient.scoped().ping() is True
    assert resilient.backend_name == "neo4j"
    assert [name for name, _ in primary.calls[calls_before:]] == ["ping", "initialize"]