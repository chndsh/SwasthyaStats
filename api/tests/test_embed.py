from app.pipeline.embed import EmbedEngine, observation_summary, get_embed_engine
from app.models import Observation
import datetime


def test_embed_returns_384_floats():
    engine = EmbedEngine(model_name="multilingual-e5-small")
    vecs = engine.embed(["Hemoglobin 13.2 g/dL"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 384
    assert all(isinstance(v, float) for v in vecs[0])


def test_observation_summary_full():
    obs = Observation(
        test_name="HbA1c",
        value_num=6.8,
        unit="%",
        collected_at=datetime.date(2026, 10, 14),
        ref_low=4.0,
        ref_high=5.6,
    )
    assert observation_summary(obs) == "HbA1c 6.8 % on 2026-10-14 (ref 4.0–5.6)"


def test_observation_summary_nulls():
    obs = Observation(
        test_name="Glucose",
        value_num=None,
        unit=None,
        collected_at=None,
        ref_low=None,
        ref_high=None,
    )
    result = observation_summary(obs)
    assert "Glucose" in result
    assert "?" in result


def test_get_embed_engine_singleton():
    a = get_embed_engine()
    b = get_embed_engine()
    assert a is b
