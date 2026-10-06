"""Same behavioural contract for every GraphRepository backend. Neo4j runs only with
RUN_INTEGRATION=1 and a reachable instance (docker compose up -d)."""
import os
import uuid
import pytest
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.models import CandidateCorrection, CandidateFact, FactType, Profile


def _neo4j_repo():
    from app.brain.neo4j_repository import Neo4jGraphRepository

    repo = Neo4jGraphRepository(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "astrochat-dev-pw"),
    )
    repo.initialize()
    return repo


@pytest.fixture(
    params=[
        "in_memory",
        pytest.param(
            "neo4j",
            marks=[
                pytest.mark.integration,
                pytest.mark.skipif(
                    os.getenv("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"
                ),
            ],
        ),
    ]
)
def repo(request):
    if request.param == "in_memory":
        repo = InMemoryGraphRepository()
        repo.initialize()
        yield repo
    else:
        repo = _neo4j_repo()
        yield repo
        repo.close()


@pytest.fixture
def user_id() -> str:
    return f"test-{uuid.uuid4()}"


def test_initialize_is_idempotent(repo):
    repo.initialize()
    assert repo.ping() is True


def test_profile_round_trip(repo, user_id):
    repo.create_profile(
        Profile(user_id=user_id, name="Rahul", dob="1995-08-15", zodiac_sign="Leo")
    )
    assert repo.get_profile(user_id).name == "Rahul"
    updated = repo.update_profile(user_id, {"dob": "1996-08-15"})
    assert (updated.name, updated.dob) == ("Rahul", "1996-08-15")
    assert repo.get_profile(f"missing-{user_id}") is None


def test_domain_query_requires_matching_life_area(repo, user_id):
    repo.upsert_facts(
        user_id,
        [
            CandidateFact(FactType.GOAL, "switch jobs", "career", "next year", 2027),
            CandidateFact(FactType.GOAL, "lose weight", "health"),
            CandidateFact(FactType.MEMORY, "I have two kids"),  # untagged
        ],
    )
    career = repo.query_facts(
        user_id, [FactType.GOAL, FactType.MEMORY], life_area="career"
    )
    assert [(f.label, f.life_area, f.target_year) for f in career] == [
        ("switch jobs", "career", 2027)
    ]
    everything = repo.query_facts(user_id, list(FactType), limit=10)
    assert {f.label for f in everything} == {
        "switch jobs",
        "lose weight",
        "I have two kids",
    }


def test_reinforce_supersede_and_retract(repo, user_id):
    repo.upsert_facts(user_id, [CandidateFact(FactType.GOAL, "switch jobs", "career")])
    [reinforced] = repo.upsert_facts(
        user_id, [CandidateFact(FactType.GOAL, "switch jobs", "career")]
    )
    assert reinforced.action == "reinforced"
    replacement = CandidateFact(FactType.GOAL, "start my own company")
    [superseded] = repo.upsert_facts(
        user_id, [], [CandidateCorrection("switch jobs", FactType.GOAL, replacement)]
    )
    assert (
        superseded.action == "superseded" and superseded.life_area == "career"
    )  # inherited
    facts = {f.label: f for f in repo.list_facts(user_id)}
    assert facts["switch jobs"].status == "superseded"
    assert facts["switch jobs"].confidence == 0.75
    assert facts["start my own company"].supersedes_id == facts["switch jobs"].id
    [retracted] = repo.upsert_facts(
        user_id, [], [CandidateCorrection("own company", None)]
    )
    assert retracted.action == "retracted"
    assert repo.query_facts(user_id, list(FactType)) == []


def test_preferences_and_interests_are_not_life_area_tagged(repo, user_id):
    repo.upsert_facts(
        user_id,
        [
            CandidateFact(FactType.PREFERENCE, "short answers", life_area="career"),
            CandidateFact(FactType.INTEREST, "entrepreneurship"),
        ],
    )
    assert all(f.life_area is None for f in repo.list_facts(user_id))
    assert [f.label for f in repo.query_facts(user_id, [FactType.INTEREST])] == [
        "entrepreneurship"
    ]