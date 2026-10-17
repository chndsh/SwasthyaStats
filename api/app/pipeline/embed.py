"""Local embedding engine using sentence-transformers."""
from __future__ import annotations

import logging
from typing import Optional

from app.models import Observation

logger = logging.getLogger(__name__)

_engine_instance: Optional["EmbedEngine"] = None


MODEL_ALIASES = {
    "multilingual-e5-small": "intfloat/multilingual-e5-small",
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
}


class EmbedEngine:
    """Wraps a SentenceTransformer model to produce 384-dim embeddings."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        resolved_model = MODEL_ALIASES.get(model_name, model_name)
        logger.info(f"Loading embedding model: {resolved_model} (requested: {model_name})")
        self._model = SentenceTransformer(resolved_model)
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, returning normalised 384-dim float vectors."""
        if not texts:
            return []
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


def observation_summary(obs: Observation) -> str:
    """Return a one-line human-readable summary of an observation."""
    value = str(obs.value_num) if obs.value_num is not None else "?"
    unit = obs.unit if obs.unit is not None else "?"
    date = str(obs.collected_at) if obs.collected_at is not None else "?"
    ref_low = str(obs.ref_low) if obs.ref_low is not None else "?"
    ref_high = str(obs.ref_high) if obs.ref_high is not None else "?"
    return f"{obs.test_name} {value} {unit} on {date} (ref {ref_low}\u2013{ref_high})"


def get_embed_engine() -> EmbedEngine:
    """Return or create the module-level EmbedEngine singleton.

    Reads embed.model from the database on first call, then caches the engine.
    """
    global _engine_instance
    if _engine_instance is None:
        model_name = "multilingual-e5-small"  # default
        try:
            from app.db import SessionLocal
            from app.services.settings import SettingsService

            db = SessionLocal()
            try:
                svc = SettingsService(db)
                model_name = svc.get_setting_value("embed.model", "multilingual-e5-small")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not read embed.model from DB, using default: {e}")
        _engine_instance = EmbedEngine(model_name=model_name)
    return _engine_instance
