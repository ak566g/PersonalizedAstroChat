import pytest
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.models import CandidateFact, FactType
from app.memory.context_selector import (
    FOLLOW_UP,
    GENERAL,
    MEMORY_RECALL,
    ContextSelector,
    classify_message,
)
from app.memory.life_area_classifier import classify_life_area


@pytest.mark.parametrize(
    ("message", "has_history", "expected"),
    [
        ("What should I focus on for my career?", False, "career"),
        ("What do you remember about my career goals?", False, MEMORY_RECALL),  # recall beats domain
        ("Why is my career going downhill?", True, "career"),  # domain beats follow-up
        ("Why do you say that?", True, FOLLOW_UP),
        ("Why do you say that?", False, GENERAL),  # nothing to follow up on
        ("Will my marriage be happy?", False, "relationship"),
        ("Should I invest my savings this year?", False, "finance"),
        ("Tell me about my sun sign", False, GENERAL),
    ],
)
def test_classification_precedence(message, has_history, expected):
    assert classify_message(message, has_history) == expected


def test_life_area_classifier_tags_fact_clauses():
    assert classify_life_area("I'm planning to switch jobs next year") == "career"
    assert classify_life_area("I have two kids") is None


def _repo_with_facts() -> InMemoryGraphRepository:
    repo = InMemoryGraphRepository()
    repo.upsert_facts(
        "u1",
        [
            CandidateFact(FactType.GOAL, "switch jobs", "career"),
            CandidateFact(FactType.GOAL, "lose weight", "health"),
            CandidateFact(FactType.INTEREST, "entrepreneurship"),
        ],
    )
    return repo


def test_domain_query_selects_only_that_life_area():
    bundle = ContextSelector().select(
        "u1", "What should I focus on for my career?", [], _repo_with_facts()
    )
    assert [f.label for f in bundle.facts] == ["switch jobs"]
    assert bundle.context_used == ["career_goal", "interest"]


def test_recall_ranks_focused_area_first_and_is_bounded():
    repo = _repo_with_facts()
    for i in range(10):
        repo.upsert_facts(
            "u1",
            [CandidateFact(FactType.MEMORY, f"unrelated memory number {i} xyz{i}")],
        )
    bundle = ContextSelector(top_n=5).select(
        "u1", "What do you remember about my career?", [], repo
    )
    assert len(bundle.facts) == 5
    assert bundle.facts[0].label == "switch jobs"


def test_general_question_sends_no_facts():
    bundle = ContextSelector().select(
        "u1", "Tell me about my sun sign", [], _repo_with_facts()
    )
    assert bundle.category == GENERAL and bundle.facts == []