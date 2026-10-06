import logging
from collections.abc import Sequence

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired, TransientError

from app.brain.models import LIFE_AREAS, PROFILE_FIELDS, Fact, FactType, Profile, utc_now
from app.brain.repository import FactWriteMixin, GraphUnavailableError

logger = logging.getLogger(__name__)

# Node label and ownership relationship per fact type. Labels/relationship types cannot be
# Cypher parameters, so queries interpolate only values from this fixed whitelist.
_SCHEMA = {
    FactType.GOAL: ("Goal", "HAS_GOAL"),
    FactType.PREFERENCE: ("Preference", "PREFERS"),
    FactType.INTEREST: ("Interest", "INTERESTED_IN"),
    FactType.MEMORY: ("Memory", "HAS_MEMORY"),
}

_TYPE_BY_LABEL = {label: fact_type for fact_type, (label, _) in _SCHEMA.items()}

_CONSTRAINTS = [
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
    "CREATE CONSTRAINT life_area_name_unique IF NOT EXISTS FOR (l:LifeArea) REQUIRE l.name IS UNIQUE",
    *(
        f"CREATE CONSTRAINT {label.lower()}_id_unique IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        for label, _ in _SCHEMA.values()
    ),
]

_LINK_LIFE_AREA = """
WITH f
FOREACH (area IN CASE WHEN $life_area IS NULL THEN [] ELSE [$life_area] END |
    MERGE (la:LifeArea {name: area})
    MERGE (f)-[:RELATES_TO]->(la))
"""

_FACT_RETURN = """
OPTIONAL MATCH (f)-[:SUPERSEDES]->(old)
RETURN f, labels(f) AS labels, la.name AS life_area, old.id AS supersedes_id
"""


class Neo4jGraphRepository(FactWriteMixin):
    def __init__(self, uri: str, user: str, password: str) -> None:
        # Short timeouts so an outage degrades to the fallback quickly instead of hanging requests.
        self._driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=3.0,
            connection_acquisition_timeout=5.0,
            max_transaction_retry_time=2.0,
        )

    def close(self) -> None:
        self._driver.close()

    def _run(self, query: str, **params) -> list:
        try:
            records, _, _ = self._driver.execute_query(query, parameters_=params)
            return records
        except (ServiceUnavailable, SessionExpired, AuthError, TransientError) as exc:
            raise GraphUnavailableError(str(exc)) from exc

    def initialize(self) -> None:
        for statement in _CONSTRAINTS:
            self._run(statement)
        self._run(
            "UNWIND $areas AS name MERGE (:LifeArea {name: name})",
            areas=list(LIFE_AREAS),
        )

    def ping(self) -> bool:
        self._run("RETURN 1")
        return True

    def create_profile(self, profile: Profile) -> Profile:
        props = {f: getattr(profile, f) for f in (*PROFILE_FIELDS, "zodiac_sign")}
        return self._write_profile(profile.user_id, props)

    def get_profile(self, user_id: str) -> Profile | None:
        records = self._run("MATCH (u:User {user_id: $user_id}) RETURN u", user_id=user_id)
        return _to_profile(records[0]["u"]) if records else None

    def update_profile(self, user_id: str, fields: dict) -> Profile:
        return self._write_profile(user_id, fields)

    def _write_profile(self, user_id: str, props: dict) -> Profile:
        records = self._run(
            """
            MERGE (u:User {user_id: $user_id})
            ON CREATE SET u.created_at = $now
            SET u += $props, u.updated_at = $now
            RETURN u
            """,
            user_id=user_id,
            props=props,
            now=utc_now(),
        )
        return _to_profile(records[0]["u"])

    def query_facts(
        self,
        user_id: str,
        fact_types: Sequence[FactType],
        life_area: str | None = None,
        limit: int = 5,
    ) -> list[Fact]:
        # Domain queries require the RELATES_TO hop (non-optional), so untagged facts are excluded.
        area_clause = (
            "MATCH (f)-[:RELATES_TO]->(la:LifeArea {name: $life_area})"
            if life_area
            else "OPTIONAL MATCH (f)-[:RELATES_TO]->(la:LifeArea)"
        )
        records = self._run(
            f"""
            MATCH (u:User {{user_id: $user_id}})-[r]->(f)
            WHERE type(r) IN $rels AND f.status = 'active'
            {area_clause}
            {_FACT_RETURN}
            ORDER BY f.confidence DESC, f.updated_at DESC
            LIMIT $limit
            """,
            user_id=user_id,
            rels=_rels(fact_types),
            life_area=life_area,
            limit=limit,
        )
        return [_to_fact(r) for r in records]

    def list_facts(self, user_id: str) -> list[Fact]:
        records = self._run(
            f"""
            MATCH (u:User {{user_id: $user_id}})-[r]->(f)
            WHERE type(r) IN $rels
            OPTIONAL MATCH (f)-[:RELATES_TO]->(la:LifeArea)
            {_FACT_RETURN}
            ORDER BY f.created_at
            """,
            user_id=user_id,
            rels=_rels(list(FactType)),
        )
        return [_to_fact(r) for r in records]

    def _active_facts(self, user_id: str, fact_types: Sequence[FactType]) -> list[Fact]:
        return self.query_facts(user_id, fact_types, limit=1000)

    def _create_fact(self, user_id: str, fact: Fact) -> None:
        label, rel = _SCHEMA[fact.fact_type]
        self._run(
            f"""
            MERGE (u:User {{user_id: $user_id}})
            ON CREATE SET u.created_at = $now, u.updated_at = $now
            CREATE (u)-[:{rel}]->(f:{label} $props)
            {_LINK_LIFE_AREA}
            """,
            user_id=user_id,
            props=_fact_props(fact),
            life_area=fact.life_area,
            now=fact.created_at,
        )

    def _reinforce_fact(self, fact, confidence, timeframe, target_year, now) -> None:
        label, _ = _SCHEMA[fact.fact_type]
        self._run(
            f"""
            MATCH (f:{label} {{id: $id}})
            SET f.confidence = $confidence, f.timeframe = $timeframe,
                f.target_year = $target_year, f.updated_at = $now
            """,
            id=fact.id,
            confidence=confidence,
            timeframe=timeframe,
            target_year=target_year,
            now=now,
        )

    def _supersede_fact(self, user_id: str, old: Fact, new: Fact) -> None:
        old_label, _ = _SCHEMA[old.fact_type]
        label, rel = _SCHEMA[new.fact_type]
        self._run(
            f"""
            MATCH (u:User {{user_id: $user_id}})-->(old:{old_label} {{id: $old_id}})
            SET old.status = 'superseded', old.updated_at = $now
            CREATE (u)-[:{rel}]->(f:{label} $props)
            CREATE (f)-[:SUPERSEDES]->(old)
            {_LINK_LIFE_AREA}
            """,
            user_id=user_id,
            old_id=old.id,
            props=_fact_props(new),
            life_area=new.life_area,
            now=new.created_at,
        )

    def _retract_fact(self, fact: Fact, now: str) -> None:
        label, _ = _SCHEMA[fact.fact_type]
        self._run(
            f"MATCH (f:{label} {{id: $id}}) SET f.status = 'retracted', f.updated_at = $now",
            id=fact.id,
            now=now,
        )


def _rels(fact_types: Sequence[FactType]) -> list[str]:
    return [_SCHEMA[t][1] for t in fact_types]


def _fact_props(fact: Fact) -> dict:
    props = {
        "id": fact.id,
        "label": fact.label,
        "confidence": fact.confidence,
        "status": fact.status,
        "created_at": fact.created_at,
        "updated_at": fact.updated_at,
        "timeframe": fact.timeframe,
        "target_year": fact.target_year,
    }
    return {k: v for k, v in props.items() if v is not None}


def _to_fact(record) -> Fact:
    node = dict(record["f"])
    fact_type = next(_TYPE_BY_LABEL[label] for label in record["labels"] if label in _TYPE_BY_LABEL)
    return Fact(
        id=node["id"],
        fact_type=fact_type,
        label=node["label"],
        confidence=node["confidence"],
        status=node["status"],
        created_at=node["created_at"],
        updated_at=node["updated_at"],
        life_area=record["life_area"],
        timeframe=node.get("timeframe"),
        target_year=node.get("target_year"),
        supersedes_id=record["supersedes_id"],
    )


def _to_profile(node) -> Profile:
    data = dict(node)
    return Profile(
        user_id=data["user_id"],
        **{f: data.get(f) for f in (*PROFILE_FIELDS, "zodiac_sign", "created_at", "updated_at")},
    )