import re
import json
import time
import logging
import httpx
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import LlmCall
from app.services.settings import SettingsService
from app.llm.keypool import KeyPool, KeyState

logger = logging.getLogger(__name__)


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
    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self.settings_service = SettingsService(db, user_id=user_id)

    def _get_daily_token_usage(self) -> int:
        from datetime import datetime, timezone
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        total = (
            self.db.query(func.coalesce(func.sum(LlmCall.prompt_tokens + LlmCall.completion_tokens), 0))
            .filter(
                LlmCall.created_at >= today_start,
                *(
                    [LlmCall.user_id == self.user_id]
                    if self.user_id is not None
                    else []
                ),
            )
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
        max_tokens: Optional[int] = None,
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
        if max_tokens is not None:
            payload[token_param] = max_tokens
        elif purpose == "route":
            # Routing queries only need a small token budget for tool calls
            payload[token_param] = min(settings.llm_max_output_tokens, 400)
        elif "groq.com" in base_url and settings.llm_max_output_tokens > 1000 and "qwen" in model.lower():
            # Groq free tier enforces strict 1000 OTPM on Qwen models
            payload[token_param] = 1000
        else:
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
                err_detail = f": {last_error}" if last_error else ""
                raise ValueError(f"All configured API keys are currently exhausted, rate-limited, or invalid{err_detail}")

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
                        user_id=self.user_id,
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

                elif resp.status_code == 400 and json_schema and payload.get("response_format", {}).get("type") == "json_schema":
                    logger.warning(f"Provider rejected json_schema with HTTP 400: {resp.text}. Falling back to json_object.")
                    payload["response_format"] = {"type": "json_object"}
                    continue

                elif resp.status_code in (401, 403):
                    key_pool.mark_bad_auth(key_state.key)
                    last_error = f"Authentication failed on key ({key_state.label}): {resp.text}"
                    continue

                elif resp.status_code == 429:
                    # Check if 429 is due to OTPM limit exceeding max_tokens
                    limit_match = re.search(r"Limit\s+(\d+)", resp.text)
                    if ("reduce max_tokens" in resp.text or "OTPM" in resp.text) and limit_match:
                        enforced_limit = int(limit_match.group(1))
                        current_toks = payload.get(token_param, 0)
                        if current_toks > enforced_limit:
                            new_toks = max(100, enforced_limit - 10)
                            logger.info(
                                f"Reducing {token_param} from {current_toks} to {new_toks} "
                                f"per provider OTPM limit."
                            )
                            payload[token_param] = new_toks
                            continue

                    retry_after = 5.0
                    header_val = resp.headers.get("retry-after")
                    if header_val:
                        try:
                            retry_after = float(header_val)
                        except ValueError:
                            pass
                    key_pool.mark_rate_limited(key_state.key, retry_after)
                    last_error = f"Rate limited on key ({key_state.label}). Waiting {retry_after}s: {resp.text}"
                    if len(keys) == 1 and attempt < max_attempts - 1:
                        logger.info(f"Single key rate limited; sleeping {retry_after}s before retry.")
                        time.sleep(retry_after)
                    continue


                else:
                    last_error = f"HTTP {resp.status_code} from provider: {resp.text}"
                    time.sleep(1)

            except Exception as e:
                last_error = str(e)
                time.sleep(1)

        raise RuntimeError(f"LLM request failed after attempts: {last_error}")
