import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Date,
    ForeignKey,
    Text,
    ARRAY,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="Default Patient")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="patient", cascade="all, delete-orphan")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    is_secret = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    status = Column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
    )  # queued | normalizing | ocr | extracting | needs_review | confirmed | failed | rate_limited
    doc_type = Column(String(50), nullable=True, default="lab_report")
    doctor_name = Column(String(255), nullable=True)
    doc_date = Column(Date, nullable=True)
    ocr_text = Column(Text, nullable=True)
    ocr_lines = Column(JSONB, nullable=True)  # list of {id, page, text, bbox, conf, row_id}
    page_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    patient = relationship("Patient", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_no = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    image_path = Column(String(500), nullable=False)
    original_path = Column(String(500), nullable=True)

    document = relationship("Document", back_populates="pages")


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    structured_mode = Column(String(50), nullable=True)
    input_hash = Column(String(64), nullable=True, index=True)
    raw_json = Column(JSONB, nullable=True)
    field_confidence = Column(JSONB, nullable=True)
    reviewer_edits = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="extractions")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    test_name = Column(String(255), nullable=False, index=True)
    canonical_test_id = Column(String(100), nullable=True, index=True)
    value_num = Column(Float, nullable=True)
    value_text = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=True)
    ref_low = Column(Float, nullable=True)
    ref_high = Column(Float, nullable=True)
    flag = Column(String(20), nullable=True)  # low | normal | high | critical
    collected_at = Column(Date, nullable=True, index=True)
    page_no = Column(Integer, default=1, nullable=False)
    source_line_ids = Column(ARRAY(Integer), nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending | confirmed

    patient = relationship("Patient", back_populates="observations")
    document = relationship("Document", back_populates="observations")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    embed_model = Column(String(100), nullable=False)
    embedding = Column(Vector(384), nullable=True)  # multilingual-e5-small (384)
    page = Column(Integer, default=1, nullable=False)

    document = relationship("Document", back_populates="chunks")


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True, index=True)
    purpose = Column(String(50), nullable=False)  # extract | route | answer | probe
    model = Column(String(100), nullable=False)
    key_label = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False)  # success | error | rate_limited
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
