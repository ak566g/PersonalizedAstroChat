from datetime import date
import pytest
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.matching import best_match, similarity
from app.brain.models import CandidateFact, FactType
from app.memory.extractor import MemoryExtractor
from app.tests.conftest import brain, chat

extractor = MemoryExtractor(today=lambda: date(2026, 10, 5))


def test_flagship_message_yields_profile_and_goal():
    result = extractor.extract(
        "My name is Rahul. I was born on 15 August 1995 in Delhi. I'm planning to switch jobs next year."
    )
    assert result.profile.fields == {
        "name": "Rahul",
        "dob": "1995-08-15",
        "birth_place": "Delhi",
    }
    [goal] = result.facts
    assert (goal.fact_type, goal.label, goal.life_area, goal.target_year) == (
        FactType.GOAL,
        "switch jobs",
        "career",
        2027,
    )


def test_month_scale_goal_keeps_timeframe_without_target_year():
    [goal] = extractor.extract(
        "I'm preparing for a product management interview next month."
    ).facts
    assert (goal.label, goal.timeframe, goal.target_year) == (
        "product management interview",
        "next month",
        None,
    )


@pytest.mark.parametrize(
    ("message", "fact_type", "label"),
    [
        ("I prefer short, direct answers", FactType.PREFERENCE, "short, direct answers"),
        (
            "I'm really interested in entrepreneurship",
            FactType.INTEREST,
            "entrepreneurship",
        ),
        (
            "I work as a software engineer at Infosys",
            FactType.MEMORY,
            "I work as a software engineer at Infosys",
        ),
        ("My goal is to run a marathon in 2027", FactType.GOAL, "run a marathon"),
    ],
)
def test_structured_fact_types(message, fact_type, label):
    [fact] = extractor.extract(message).facts
    assert (fact.fact_type, fact.label) == (fact_type, label)


def test_language_preference_goes_to_profile_not_a_preference_node():
    result = extractor.extract("Please talk to me in Hindi")
    assert result.profile.fields == {"preferred_language": "Hindi"}
    assert result.facts == []


@pytest.mark.parametrize(
    "message",
    [
        "Why do you say that?",
        "What should I focus on for my career?",
        "Hello! How are you?",
        "Thanks, that's helpful",
        "I want to know what my horoscope says",
        "Tell me about Leo traits",
    ],
)
def test_12_non_informative_messages_store_nothing(message):
    assert extractor.extract(message).is_empty()


def test_12_api_does_not_store_questions_or_small_talk(client, rahul):
    headers, _ = rahul
    for message in (
        "Why do you say that?",
        "Hello! How are you?",
        "What should I focus on for my career?",
    ):
        assert chat(client, headers, message)["memory_updates"] == []
        assert brain(client, headers) == []


def test_statement_before_a_trailing_question_is_kept():
    [goal] = extractor.extract(
        "I'm planning to switch jobs next year, what do you think?"
    ).facts
    assert goal.label == "switch jobs"


def test_negation_with_replacement_becomes_one_correction():
    result = extractor.extract(
        "Actually, I don't want to switch jobs anymore — I want to start my own company instead"
    )
    assert result.facts == []
    [correction] = result.corrections
    assert (correction.target_hint, correction.fact_type) == (
        "switch jobs",
        FactType.GOAL,
    )
    assert correction.replacement.label == "start my own company"


def test_07_correcting_a_goal_supersedes_it(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.")
    body = chat(
        client,
        headers,
        "Actually, I don't want to switch jobs anymore — I want to start my own company instead",
    )
    assert [u["action"] for u in body["memory_updates"]] == ["superseded"]
    facts = {f["label"]: f for f in brain(client, headers)}
    old, new = facts["switch jobs"], facts["start my own company"]
    assert old["status"] == "superseded"
    assert new["status"] == "active" and new["supersedes_id"] == old["id"]
    assert new["life_area"] == "career"
    recall = chat(
        client,
        headers,
        "What do you remember about my career goals?",
        session_id="later",
    )
    assert (
        "start my own company" in recall["response"]
        and "switch jobs" not in recall["response"]
    )


def test_negation_without_replacement_retracts(client, rahul):
    headers, _ = rahul
    chat(client, headers, "I'm planning to switch jobs next year.")
    body = chat(client, headers, "I'm no longer planning to switch jobs.")
    assert [u["action"] for u in body["memory_updates"]] == ["retracted"]
    assert brain(client, headers)[0]["status"] == "retracted"


def test_correction_with_no_matching_fact_is_dropped_but_replacement_is_kept():
    repo = InMemoryGraphRepository()
    result = extractor.extract(
        "I don't want to become a lawyer anymore. I want to study design."
    )
    updates = repo.upsert_facts("u1", result.facts, result.corrections)
    assert [(u.action, u.label) for u in updates] == [("created", "study design")]


def test_restating_a_fact_reinforces_instead_of_duplicating():
    repo = InMemoryGraphRepository()
    goal = CandidateFact(FactType.GOAL, "switch jobs", "career", "next year", 2027)
    repo.upsert_facts("u1", [goal])
    [update] = repo.upsert_facts(
        "u1", [CandidateFact(FactType.GOAL, "switch my job", "career")]
    )
    assert update.action == "reinforced" and update.details["confidence"] == 0.75
    [fact] = repo.list_facts("u1")
    assert (fact.confidence, fact.target_year) == (
        0.75,
        2027,
    )  # earlier timeframe preserved


def test_confidence_is_capped_at_one():
    repo = InMemoryGraphRepository()
    for _ in range(6):
        repo.upsert_facts("u1", [CandidateFact(FactType.INTEREST, "entrepreneurship")])
    assert repo.list_facts("u1")[0].confidence == 1.0


def test_matching_prefers_the_most_similar_fact():
    repo = InMemoryGraphRepository()
    repo.upsert_facts(
        "u1",
        [
            CandidateFact(FactType.GOAL, "switch jobs"),
            CandidateFact(FactType.GOAL, "buy a house"),
        ],
    )
    target = best_match(repo.list_facts("u1"), "switch jobs anymore")
    assert target.label == "switch jobs"
    assert similarity("start my own company", "switch jobs") == 0