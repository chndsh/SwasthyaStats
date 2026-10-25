"""RAG database tools."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func

from app.models import Observation, Chunk
from app.services.documents import get_lab_dictionary
from app.pipeline.normalize import _find_canonical_test_id
from app.pipeline.embed import get_embed_engine

logger = logging.getLogger(__name__)


def list_tests(db: Session, user_id: int | None = None) -> List[Dict[str, Any]]:
    """List distinct tests with count and latest date for confirmed observations."""
    lab_dict = get_lab_dictionary()
    q = db.query(Observation).filter(Observation.status == "confirmed")
    if user_id is not None:
        q = q.filter(Observation.user_id == user_id)
    obs_list = q.order_by(Observation.collected_at.desc().nullslast(), Observation.id.desc()).all()

    tests_map: Dict[str, Dict[str, Any]] = {}
    for obs in obs_list:
        canon_id = obs.canonical_test_id or _find_canonical_test_id(obs.test_name, lab_dict)
        if canon_id and canon_id in lab_dict:
            display_name = lab_dict[canon_id].get("name", obs.test_name)
            key = canon_id
        else:
            display_name = obs.test_name
            key = obs.test_name.strip().lower()

        if key not in tests_map:
            tests_map[key] = {
                "test_name": display_name,
                "canonical_test_id": canon_id,
                "count": 1,
                "latest_date": obs.collected_at,
            }
        else:
            tests_map[key]["count"] += 1
            if obs.collected_at and (not tests_map[key]["latest_date"] or obs.collected_at > tests_map[key]["latest_date"]):
                tests_map[key]["latest_date"] = obs.collected_at

    result = list(tests_map.values())
    result.sort(key=lambda t: t["test_name"].lower())
    return result


def get_observations(
    db: Session,
    test: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Get confirmed observations for a test, matching alias or raw name."""
    lab_dict = get_lab_dictionary()
    clean_test = test.strip().lower()
    canon_id = clean_test if clean_test in lab_dict else _find_canonical_test_id(test, lab_dict)

    query = db.query(Observation).filter(Observation.status == "confirmed")
    if user_id is not None:
        query = query.filter(Observation.user_id == user_id)

    if canon_id:
        alias_names = [clean_test, canon_id.lower()]
        dict_entry = lab_dict.get(canon_id, {})
        if dict_entry.get("name"):
            alias_names.append(dict_entry["name"].lower())
        for a in dict_entry.get("aliases", []):
            alias_names.append(a.lower())

        conditions = [Observation.canonical_test_id == canon_id]
        for name in set(alias_names):
            conditions.append(func.lower(Observation.test_name).like(f"%{name}%"))
        query = query.filter(or_(*conditions))
    else:
        query = query.filter(func.lower(Observation.test_name).like(f"%{clean_test}%"))

    if from_date:
        query = query.filter(Observation.collected_at >= from_date)
    if to_date:
        query = query.filter(Observation.collected_at <= to_date)

    obs_records = query.order_by(Observation.collected_at.asc().nullslast(), Observation.id.asc()).all()

    results: List[Dict[str, Any]] = []
    for o in obs_records:
        results.append({
            "id": o.id,
            "document_id": o.document_id,
            "page_no": o.page_no,
            "test_name": o.test_name,
            "canonical_test_id": o.canonical_test_id,
            "value_num": o.value_num,
            "value_text": o.value_text,
            "unit": o.unit,
            "ref_low": o.ref_low,
            "ref_high": o.ref_high,
            "flag": o.flag,
            "collected_at": o.collected_at,
        })
    return results


def get_latest_observations(db: Session, tests: List[str], user_id: int | None = None) -> List[Dict[str, Any]]:
    """Return the single most recent confirmed observation for each test in tests."""
    results: List[Dict[str, Any]] = []
    for t in tests:
        obs = get_observations(db, t, user_id=user_id)
        if obs:
            sorted_obs = sorted(
                obs,
                key=lambda x: (x["collected_at"] is not None, x["collected_at"] or date.min, x["id"]),
                reverse=True,
            )
            results.append(sorted_obs[0])
    return results


def search_documents(db: Session, query: str, top_k: int = 5, user_id: int | None = None) -> List[Dict[str, Any]]:
    """Hybrid search on chunks using pgvector cosine distance and pg_trgm similarity via RRF."""
    from app.pipeline.embed import get_embed_engine
    engine = get_embed_engine()
    vecs = engine.embed([query])
    if not vecs:
        return []
    q_vec = vecs[0]

    # Vector cosine similarity using cast(:q_vec, Vector)
    vec_query = (
        db.query(
            Chunk.id,
            Chunk.document_id,
            Chunk.page,
            Chunk.text,
            (1 - Chunk.embedding.cosine_distance(q_vec)).label("sim"),
        )
        .filter(Chunk.embedding.isnot(None))
    )
    if user_id is not None:
        vec_query = vec_query.filter(Chunk.user_id == user_id)
    chunk_rows = vec_query.order_by(Chunk.embedding.cosine_distance(q_vec).asc()).limit(top_k * 2).all()

    # Trigram similarity
    if user_id is not None:
        trgm_sql = text("""
            SELECT id, document_id, page, text, similarity(text, :query) AS sim
            FROM chunks
            WHERE user_id = :uid AND similarity(text, :query) > 0.05
            ORDER BY sim DESC
            LIMIT :k
        """)
        trgm_rows = db.execute(trgm_sql, {"query": query, "k": top_k * 2, "uid": user_id}).fetchall()
    else:
        trgm_sql = text("""
            SELECT id, document_id, page, text, similarity(text, :query) AS sim
            FROM chunks
            WHERE similarity(text, :query) > 0.05
            ORDER BY sim DESC
            LIMIT :k
        """)
        trgm_rows = db.execute(trgm_sql, {"query": query, "k": top_k * 2}).fetchall()

    rrf_scores: Dict[int, float] = {}
    chunk_map: Dict[int, Dict[str, Any]] = {}

    for rank, row in enumerate(chunk_rows):
        cid = row.id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + (rank + 1)))
        chunk_map[cid] = {
            "chunk_id": cid,
            "document_id": row.document_id,
            "page": row.page,
            "text": row.text,
        }

    for rank, row in enumerate(trgm_rows):
        cid = row.id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + (rank + 1)))
        if cid not in chunk_map:
            chunk_map[cid] = {
                "chunk_id": cid,
                "document_id": row.document_id,
                "page": row.page,
                "text": row.text,
            }

    sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    ranked_results: List[Dict[str, Any]] = []
    for cid in sorted_cids[:top_k]:
        item = dict(chunk_map[cid])
        item["score"] = round(rrf_scores[cid], 5)
        ranked_results.append(item)

    return ranked_results
