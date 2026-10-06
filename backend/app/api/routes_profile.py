from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_graph, require_user
from app.api.schemas import BrainResponse, FactOut, ProfileFields, ProfileResponse
from app.brain.models import Profile
from app.brain.resilient_repository import ScopedGraph
from app.profile.service import ProfileService

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_me(user: CurrentUser = Depends(require_user), graph: ScopedGraph = Depends(get_graph)) -> ProfileResponse:
    return _profile_response(ProfileService(graph).get(user.user_id), graph)


@router.patch("", response_model=ProfileResponse)
def update_me(
    body: ProfileFields,
    user: CurrentUser = Depends(require_user),
    graph: ScopedGraph = Depends(get_graph),
) -> ProfileResponse:
    profile = ProfileService(graph).update(user.user_id, body.profile_values(only_set=True))
    return _profile_response(profile, graph)


@router.get("/brain", response_model=BrainResponse)
def get_brain(user: CurrentUser = Depends(require_user), graph: ScopedGraph = Depends(get_graph)) -> BrainResponse:
    facts = [
        FactOut(
            id=f.id, type=f.fact_type.value, label=f.label, status=f.status, confidence=f.confidence,
            life_area=f.life_area, timeframe=f.timeframe, target_year=f.target_year,
            supersedes_id=f.supersedes_id, created_at=f.created_at, updated_at=f.updated_at,
        )
        for f in graph.list_facts(user.user_id)
    ]
    return BrainResponse(user_id=user.user_id, facts=facts, degraded=graph.degraded)


def _profile_response(profile: Profile, graph: ScopedGraph) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        dob=profile.dob,
        time_of_birth=profile.time_of_birth,
        birth_place=profile.birth_place,
        preferred_language=profile.preferred_language,
        zodiac_sign=profile.zodiac_sign,
        degraded=graph.degraded,
    )