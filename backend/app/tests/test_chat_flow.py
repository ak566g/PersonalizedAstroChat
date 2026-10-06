from datetime import date
from app.brain.models import FactType
from app.tests.conftest import brain, chat, signup


def test_01_new_user_first_chat_has_minimal_context(client):
    headers, _ = signup(client, "new@example.com")
    body = chat(client, headers, "Hello!")
    assert body["response"]
    assert body["context_used"] == []
    assert body["memory_updates"] == []
    assert body["degraded"] is False


def test_02_goal_statement_becomes_long_term_memory(client, rahul):
    headers, _ = rahul
    body = chat(client, headers, "I'm planning to switch jobs next year.")
    assert [u["action"] for u in body["memory_updates"]] == ["created"]
    [goal] = brain(client, headers)
    assert goal["type"] == "goal"
    assert goal["label"] == "switch jobs"
    assert goal["timeframe"] == "next year"
    assert goal["target_year"] == date.today().year + 1
    assert goal["life_area"] == "career"  # RELATES_TO edge exists, so domain retrieval can find it


def test_03_memory_recall_retrieves_stored_goal_in_new_session(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.", session_id="first")
    body = chat(
        client,
        headers,
        "What do you remember about my career goals?",
        session_id="second",
    )
    assert body["intent"] == "memory_recall"
    assert "career_goal" in body["context_used"]
    assert "switch jobs" in body["response"]


def test_04_follow_up_uses_short_term_context_not_the_graph(client, rahul, graph, llm):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.")
    chat(client, headers, "What should I focus on for my career?")
    graph.calls.clear()
    body = chat(client, headers, "Why do you say that?")
    assert body["intent"] == "follow_up"
    assert "recent_conversation" in body["context_used"]
    assert not any(k.endswith("_goal") for k in body["context_used"])
    fact_queries = [args for name, args in graph.calls if name == "query_facts"]
    assert all(FactType.GOAL not in args[1] for args in fact_queries)
    # The previous assistant answer reached the LLM as history.
    assert any(
        t.role == "assistant" and "career" in t.content for t in llm.requests[-1].history
    )


def test_05_new_session_still_personalizes_from_shared_brain(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.", session_id="monday")
    body = chat(
        client,
        headers,
        "What should I focus on for my career?",
        session_id="friday",
    )
    assert "career_goal" in body["context_used"]
    assert "recent_conversation" not in body["context_used"]  # nothing carried over in short-term
    assert "switch jobs" in body["response"]


def test_06_irrelevant_memory_is_excluded(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.")
    body = chat(
        client,
        headers,
        "How can I improve my health and sleep?",
        session_id="other",
    )
    assert body["intent"] == "health"
    assert "career_goal" not in body["context_used"]
    assert "switch jobs" not in body["response"]


def test_09_missing_profile_information_still_answers(client):
    headers, _ = signup(client, "anon@example.com")
    body = chat(client, headers, "What should I focus on for my career?")
    assert body["response"]
    assert "zodiac_sign" not in body["context_used"]
    assert "user_profile" not in body["context_used"]


def test_14_two_users_never_see_each_others_long_term_memory(client):
    alice, _ = signup(client, "alice@example.com", name="Alice")
    bob, _ = signup(client, "bob@example.com", name="Bob")
    chat(client, alice, "I'm planning to open a bakery business next year.")
    chat(client, bob, "I'm preparing for a product management interview next month.")
    alice_reply = chat(
        client, alice, "What do you remember about my career goals?", session_id="r"
    )
    bob_reply = chat(
        client, bob, "What do you remember about my career goals?", session_id="r"
    )
    assert (
        "bakery" in alice_reply["response"]
        and "product management" not in alice_reply["response"]
    )
    assert (
        "product management" in bob_reply["response"]
        and "bakery" not in bob_reply["response"]
    )


def test_16_same_session_id_from_two_users_keeps_histories_separate(client):
    alice, alice_id = signup(client, "alice2@example.com")
    bob, bob_id = signup(client, "bob2@example.com")
    shared = "shared-session"
    chat(client, alice, "I'm planning to switch jobs next year.", session_id=shared)
    chat(client, bob, "Hello there", session_id=shared)
    chat(client, bob, "Tell me more", session_id=shared)  # second message in the colliding session
    store = client.container.short_term
    bob_turns = store.recent(bob_id, shared, 50)
    alice_turns = store.recent(alice_id, shared, 50)
    assert [t.content for t in bob_turns if t.role == "user"] == [
        "Hello there",
        "Tell me more",
    ]
    assert [t.content for t in alice_turns if t.role == "user"] == [
        "I'm planning to switch jobs next year."
    ]


def test_spec_example_conversation_end_to_end(client):
    headers, _ = signup(client, "rahul.spec@example.com")
    first = chat(
        client,
        headers,
        "My name is Rahul. I was born on 15 August 1995 in Delhi. I'm planning to switch jobs next year.",
    )
    assert {(u["action"], u["label"]) for u in first["memory_updates"]} >= {
        ("profile_updated", "name"),
        ("profile_updated", "dob"),
        ("profile_updated", "birth_place"),
        ("created", "switch jobs"),
    }
    me = client.get("/me", headers=headers).json()
    assert (me["name"], me["dob"], me["birth_place"], me["zodiac_sign"]) == (
        "Rahul",
        "1995-08-15",
        "Delhi",
        "Leo",
    )
    focus = chat(client, headers, "What should I focus on for my career?")
    assert focus["context_used"][:2] == ["career_goal", "user_profile"]
    assert "Leo" in focus["response"] and "switch jobs" in focus["response"]
    why = chat(client, headers, "Why do you say that?")
    assert why["intent"] == "follow_up"
    recall = chat(
        client,
        headers,
        "What do you remember about my career goals?",
        session_id="new-conversation",
    )
    assert str(date.today().year + 1) in recall["response"]