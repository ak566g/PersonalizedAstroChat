from datetime import date
import pytest
from app.profile.zodiac import sun_sign
from app.tests.conftest import brain, chat, signup


@pytest.mark.parametrize(
    ("dob", "sign"),
    [
        (date(1995, 8, 15), "Leo"),
        (date(1990, 1, 1), "Capricorn"),
        (date(1990, 1, 20), "Aquarius"),
        (date(1990, 3, 20), "Pisces"),
        (date(1990, 3, 21), "Aries"),
        (date(1990, 12, 22), "Capricorn"),
    ],
)
def test_sun_sign_boundaries(dob, sign):
    assert sun_sign(dob) == sign


def test_signup_profile_and_zodiac(client, rahul):
    headers, user_id = rahul
    me = client.get("/me", headers=headers).json()
    assert me == {
        "user_id": user_id,
        "name": "Rahul",
        "dob": "1995-08-15",
        "time_of_birth": None,
        "birth_place": "Delhi",
        "preferred_language": None,
        "zodiac_sign": "Leo",
        "degraded": False,
    }


def test_patch_me_updates_fields_and_recomputes_zodiac(client, rahul):
    headers, _ = rahul
    response = client.patch(
        "/me",
        json={"dob": "1995-04-10", "preferred_language": "Hindi"},
        headers=headers,
    )
    assert response.status_code == 200
    me = response.json()
    assert (
        me["dob"],
        me["zodiac_sign"],
        me["preferred_language"],
        me["name"],
    ) == ("1995-04-10", "Aries", "Hindi", "Rahul")


def test_08_profile_correction_in_chat_overwrites_in_place(client, rahul):
    headers, _ = rahul
    body = chat(client, headers, "Actually I was born in 1996, not 1995")
    assert [(u["action"], u["label"]) for u in body["memory_updates"]] == [
        ("profile_updated", "dob")
    ]
    assert client.get("/me", headers=headers).json()["dob"] == "1996-08-15"
    assert (
        brain(client, headers) == []
    )  # no fact node, no SUPERSEDES chain for profile scalars


def test_language_preference_from_chat_updates_profile(client, rahul):
    headers, _ = rahul
    chat(client, headers, "Please reply in Hindi from now on")
    assert client.get("/me", headers=headers).json()["preferred_language"] == "Hindi"


def test_profile_validation(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": "x@example.com",
            "password": "long-enough",
            "dob": "2999-01-01",
            "time_of_birth": "25:00",
        },
    )
    assert response.status_code == 422
    fields = {err["loc"][-1] for err in response.json()["detail"]}
    assert fields == {"dob", "time_of_birth"}


def test_signup_with_no_profile_fields(client):
    headers, _ = signup(client, "bare@example.com")
    me = client.get("/me", headers=headers).json()
    assert me["name"] is None and me["zodiac_sign"] is None