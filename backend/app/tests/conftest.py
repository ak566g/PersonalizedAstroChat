import pytest
from fastapi.testclient import TestClient
from app.application import create_app
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.repository import GraphUnavailableError
from app.config import Settings
from app.llm.base import LLMError, LLMRequest
from app.llm.mock_provider import MockProvider

DEFAULT_PASSWORD = "correct-horse-battery"


class FlakyGraph:
    """In-memory primary graph that records calls and can simulate a Neo4j outage."""

    def __init__(self) -> None:
        self.inner = InMemoryGraphRepository()
        self.down = False
        self.calls: list[tuple[str, tuple]] = []

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if not callable(attr):
            return attr

        def call(*args, **kwargs):
            self.calls.append((name, args))
            if self.down:
                raise GraphUnavailableError("simulated outage")
            return attr(*args, **kwargs)

        return call


class SwitchableLLM(MockProvider):
    def __init__(self) -> None:
        self.fail = False
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> str:
        self.requests.append(request)
        if self.fail:
            raise LLMError("simulated provider outage")
        return super().generate(request)


@pytest.fixture
def graph() -> FlakyGraph:
    return FlakyGraph()


@pytest.fixture
def llm() -> SwitchableLLM:
    return SwitchableLLM()


@pytest.fixture
def client(tmp_path, graph, llm):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        password_hash_iterations=1_000,  # keep tests fast; production default is 310k
        graph_retry_interval_seconds=0,
    )
    app = create_app(settings, primary_graph=graph, llm=llm)
    with TestClient(app) as test_client:
        test_client.container = app.state.container
        yield test_client


def signup(
    client, email: str, password: str = DEFAULT_PASSWORD, **profile
) -> tuple[dict, str]:
    response = client.post(
        "/auth/signup", json={"email": email, "password": password, **profile}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['session_token']}"}, body["user_id"]


def chat(client, headers: dict, message: str, session_id: str = "session-1") -> dict:
    response = client.post(
        "/chat",
        json={"session_id": session_id, "message": message},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def brain(client, headers: dict) -> list[dict]:
    response = client.get("/me/brain", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["facts"]


@pytest.fixture
def rahul(client) -> tuple[dict, str]:
    return signup(
        client,
        "rahul@example.com",
        name="Rahul",
        dob="1995-08-15",
        birth_place="Delhi",
    )