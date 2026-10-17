from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime


class ApiKeyEntry(BaseModel):
    key: str
    label: Optional[str] = None


class MaskedApiKeyEntry(BaseModel):
    masked_key: str
    label: Optional[str] = None


class AppSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_api_keys: Optional[List[ApiKeyEntry]] = None
    llm_key_strategy: Optional[Literal["failover", "round_robin"]] = None
    llm_model: Optional[str] = None
    llm_model_extract: Optional[str] = None
    llm_model_ask: Optional[str] = None
    llm_structured_mode: Optional[Literal["auto", "strict_schema", "best_effort_schema", "json_object", "prompt_only"]] = None
    llm_supports_tools: Optional[bool] = None
    llm_max_tokens_param: Optional[str] = None
    llm_extra_params: Optional[Dict[str, Any]] = None
    llm_extra_headers: Optional[Dict[str, str]] = None
    llm_strip_reasoning: Optional[bool] = None
    llm_concurrency: Optional[int] = None
    llm_timeout_s: Optional[int] = None
    llm_max_output_tokens: Optional[int] = None
    llm_daily_token_cap: Optional[int] = None
    privacy_redact_pii: Optional[bool] = None
    ocr_languages: Optional[List[str]] = None
    embed_model: Optional[str] = None


class AppSettingsRead(BaseModel):
    llm_provider: str = "groq"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_keys: List[MaskedApiKeyEntry] = []
    llm_key_strategy: str = "failover"
    llm_model: str = ""
    llm_model_extract: Optional[str] = None
    llm_model_ask: Optional[str] = None
    llm_structured_mode: str = "auto"
    llm_supports_tools: bool = True
    llm_max_tokens_param: str = "max_tokens"
    llm_extra_params: Dict[str, Any] = {}
    llm_extra_headers: Dict[str, str] = {}
    llm_strip_reasoning: bool = True
    llm_concurrency: int = 2
    llm_timeout_s: int = 60
    llm_max_output_tokens: int = 2000
    llm_daily_token_cap: int = 200000
    privacy_redact_pii: bool = True
    ocr_languages: List[str] = ["en"]
    embed_model: str = "multilingual-e5-small"


class TestLlmProbeResult(BaseModel):
    label: str
    status: Literal["ok", "bad_auth", "error", "rate_limited"]
    auth_ok: bool
    latency_ms: int
    detected_structured_mode: str
    supports_tools: bool
    has_usage: bool
    has_reasoning_tags: bool
    message: Optional[str] = None


class TestLlmResponse(BaseModel):
    success: bool
    probes: List[TestLlmProbeResult]


class UsageStats(BaseModel):
    tokens_today: int
    calls_today: int
    rate_limited_documents: int
    last_call_at: Optional[datetime] = None


# --- Lab extraction Pydantic schemas (Section 10.2) ---

class LabObservationSchema(BaseModel):
    test_name: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[Literal["low", "normal", "high", "critical"]] = None
    line_ids: List[int] = []


class LabReportSchema(BaseModel):
    lab_name: Optional[str] = None
    report_date: Optional[date] = None
    observations: List[LabObservationSchema] = []


# --- Document & Page schemas (Section 13) ---

class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_no: int
    width: Optional[int] = None
    height: Optional[int] = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    filename: str
    status: str
    page_count: int
    created_at: datetime
    pages: List[DocumentPageRead] = []



class DocumentUploadResponse(BaseModel):
    id: int
    status: str
    page_count: int


# --- Review & Observation schemas ---

class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_name: str
    canonical_test_id: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[str] = None
    collected_at: Optional[date] = None
    page_no: int
    source_line_ids: Optional[List[int]] = None
    status: str
    confidence: Optional[float] = None


class ObservationPatch(BaseModel):
    test_name: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[str] = None
    collected_at: Optional[date] = None


class ExtractionRead(BaseModel):
    document_id: int
    status: str
    observations: List[ObservationRead]
    ocr_lines: List[Dict[str, Any]] = []


# --- Charts & Lab trends schemas (Week 4) ---

class LabTestSummary(BaseModel):
    test_name: str
    canonical_test_id: Optional[str] = None
    count: int
    latest_value: Optional[float] = None
    latest_unit: Optional[str] = None
    latest_flag: Optional[str] = None
    latest_date: Optional[date] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None


class ChartPoint(BaseModel):
    date: date
    value: float
    flag: Optional[str] = None
    document_id: int
    page_no: int = 1


class LabChartResponse(BaseModel):
    test_name: str
    points: List[ChartPoint] = []
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    unit: Optional[str] = None


