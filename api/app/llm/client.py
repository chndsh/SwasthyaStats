import re
import json
import time
import httpx
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import LlmCall
from app.services.settings import SettingsService
from app.llm.keypool import KeyPool, KeyState


def strip_think_tags(text: str) -> str:
    if not text:
        return ""
    # Strip <think>...</think> blocks including multi-line content
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


class LlmResponse:
    def __init__(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        model_used: str = "",
        key_label: str = "",
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms
        self.model_used = model_used
        self.key_label = key_label


class OpenAICompatClient:
    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)

    def _get_daily_token_usage(self) -> int:
        today_start = time.strftime("%Y-%m-%d 00:00:00")
        total = (
            self.db.query(func.coalesce(func.sum(LlmCall.prompt_tokens + LlmCall.completion_tokens), 0))
            .filter(LlmCall.created_at >= today_start)
            .scalar()
        )
        return int(total)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        purpose: Literal["extract", "route", "answer", "probe"],
        json_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        override_model: Optional[str] = None,
    ) -> LlmResponse:
        settings = self.settings_service.get_read_settings()
        keys = self.settings_service.get_decrypted_keys()

        if not keys:
            raise ValueError("No LLM API keys configured. Please add an API key in Settings.")

        # Check daily token cap
        daily_used = self._get_daily_token_usage()
        if daily_used >= settings.llm_daily_token_cap:
            raise ValueError(f"Daily token cap reached ({daily_used}/{settings.llm_daily_token_cap}).")

        key_pool = KeyPool(keys, strategy=settings.llm_key_strategy)  # type: ignore
        base_url = settings.llm_base_url.rstrip("/")
        model = override_model or settings.llm_model

        if not model:
            raise ValueError("No LLM model specified. Please select a model in Settings.")

        # Construct request payload
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        # Token parameter configuration
        token_param = settings.llm_max_tokens_param or "max_tokens"
        payload[token_param] = settings.llm_max_output_tokens

        # Merge extra parameters
        if settings.llm_extra_params:
            payload.update(settings.llm_extra_params)

        # Handle structured output vs tools (Never combined per Section 4.4)
        if json_schema:
            mode = settings.llm_structured_mode
            if mode in ("auto", "strict_schema"):
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "extraction", "strict": True, "schema": json_schema},
                }
            elif mode == "best_effort_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "extraction", "strict": False, "schema": json_schema},
                }
            elif mode == "json_object":
                payload["response_format"] = {"type": "json_object"}
            # prompt_only doesn't add response_format

        elif tools and settings.llm_supports_tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
        }
        if settings.llm_extra_headers:
            headers.update(settings.llm_extra_headers)

        endpoint = f"{base_url}/chat/completions"
        max_attempts = len(keys) * 2
        last_error = None

        for attempt in range(max_attempts):
            key_state = key_pool.get_key()
            if not key_state:
                raise ValueError("All configured API keys are currently exhausted, rate-limited, or invalid.")

            req_headers = dict(headers)
            req_headers["Authorization"] = f"Bearer {key_state.key}"

            start_t = time.time()
            try:
                with httpx.Client(timeout=float(settings.llm_timeout_s)) as client:
                    resp = client.post(endpoint, json=payload, headers=req_headers)

                latency_ms = int((time.time() - start_t) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    key_pool.mark_success(key_state.key)

                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    raw_content = msg.get("content") or ""

                    if settings.llm_strip_reasoning:
                        clean_content = strip_think_tags(raw_content)
                    else:
                        clean_content = raw_content

                    tool_calls = msg.get("tool_calls") or []

                    usage = data.get("usage", {})
                    p_toks = usage.get("prompt_tokens", 0)
                    c_toks = usage.get("completion_tokens", 0)

                    # Log metadata to llm_calls
                    call_log = LlmCall(
                        purpose=purpose,
                        model=model,
                        key_label=key_state.label,
                        prompt_tokens=p_toks,
                        completion_tokens=c_toks,
                        latency_ms=latency_ms,
                        status="success",
                    )
                    self.db.add(call_log)
                    self.db.commit()

                    return LlmResponse(
                        content=clean_content,
                        tool_calls=tool_calls,
                        prompt_tokens=p_toks,
                        completion_tokens=c_toks,
                        latency_ms=latency_ms,
                        model_used=model,
                        key_label=key_state.label,
                    )

                elif resp.status_code in (401, 403):
                    key_pool.mark_bad_auth(key_state.key)
                    last_error = f"Authentication failed on key ({key_state.label}): {resp.text}"
                    continue

                elif resp.status_code == 429:
                    retry_after = 60.0
                    header_val = resp.headers.get("retry-after")
                    if header_val and header_val.isdigit():
                        retry_after = float(header_val)
                    key_pool.mark_rate_limited(key_state.key, retry_after)
                    last_error = f"Rate limited on key ({key_state.label}). Waiting {retry_after}s."
                    continue

                else:
                    last_error = f"HTTP {resp.status_code} from provider: {resp.text}"
                    time.sleep(1)

            except Exception as e:
                last_error = str(e)
                time.sleep(1)

        raise RuntimeError(f"LLM request failed after attempts: {last_error}")
