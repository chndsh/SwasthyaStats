import datetime
import json
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
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db import Base


class TextOrJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return value


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="user", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")
    llm_calls = relationship("LlmCall", back_populates="user")


class RefreshTokenBlocklist(Base):
    __tablename__ = "refresh_token_blocklist"

    token_hash = Column(String(64), primary_key=True)
    expires_at = Column(DateTime(timezone=True), index=True, nullable=False)


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    is_secret = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="settings")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
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
    ocr_text = Column(Text, nullable=True)  # Fernet encrypted ciphertext
    ocr_lines = Column(JSONB, nullable=True)  # list of {id, page, text, bbox, conf, row_id}
    page_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")
    observations = relationship("Observation", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    @property
    def patient_id(self) -> int:
        return self.user_id

    @patient_id.setter
    def patient_id(self, val: int):
        self.user_id = val


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
    raw_json = Column(TextOrJSON, nullable=True)  # Encrypted JSON string or dict
    field_confidence = Column(JSONB, nullable=True)
    reviewer_edits = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="extractions")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    test_name = Column(String(255), nullable=False, index=True)
    canonical_test_id = Column(String(100), nullable=True, index=True)
    value_num = Column(Float, nullable=True)
    value_text = Column(String(255), nullable=True)  # Encrypted string
    unit = Column(String(50), nullable=True)
    ref_low = Column(Float, nullable=True)
    ref_high = Column(Float, nullable=True)
    flag = Column(String(20), nullable=True)  # low | normal | high | critical
    collected_at = Column(Date, nullable=True, index=True)
    page_no = Column(Integer, default=1, nullable=False)
    source_line_ids = Column(ARRAY(Integer), nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending | confirmed

    user = relationship("User", back_populates="observations")
    document = relationship("Document", back_populates="observations")

    @property
    def patient_id(self) -> int:
        return self.user_id

    @patient_id.setter
    def patient_id(self, val: int):
        self.user_id = val


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    embed_model = Column(String(100), nullable=False)
    embedding = Column(Vector(384), nullable=True)  # multilingual-e5-small (384)
    page = Column(Integer, default=1, nullable=False)

    user = relationship("User", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    purpose = Column(String(50), nullable=False)  # extract | route | answer | probe
    model = Column(String(100), nullable=False)
    key_label = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False)  # success | error | rate_limited
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="llm_calls")


# Backward compatibility aliases during transition
AppSetting = UserSetting
Patient = User

