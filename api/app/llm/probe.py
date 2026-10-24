import time
import httpx
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.services.settings import SettingsService
from app.schemas import TestLlmProbeResult, TestLlmResponse


def run_probe_ladder(db: Session, user_id: int | None = None) -> TestLlmResponse:
    settings_service = SettingsService(db, user_id=user_id)
    settings = settings_service.get_read_settings()
    keys = settings_service.get_decrypted_keys()

    if not keys:
        return TestLlmResponse(success=False, probes=[])

    base_url = settings.llm_base_url.rstrip("/")
    model = settings.llm_model

    probes: List[TestLlmProbeResult] = []
    overall_success = True

    for item in keys:
        key_str = item["key"]
        label = item.get("label", "key")
        headers = {"Authorization": f"Bearer {key_str}", "Content-Type": "application/json"}
        if settings.llm_extra_headers:
            headers.update(settings.llm_extra_headers)

        start_t = time.time()
        auth_ok = False
        detected_mode = "prompt_only"
        supports_tools = False
        has_usage = False
        has_reasoning = False
        status = "ok"
        message = None

        # 1. Reachability & Auth check
        try:
            with httpx.Client(timeout=15.0) as client:
                # Test a minimal completion
                resp = client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                    },
                    headers=headers,
                )
            latency_ms = int((time.time() - start_t) * 1000)

            if resp.status_code == 200:
                auth_ok = True
                data = resp.json()
                if "usage" in data:
                    has_usage = True
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if "<think>" in content:
                    has_reasoning = True
            elif resp.status_code in (401, 403):
                status = "bad_auth"
                message = f"Auth failed (HTTP {resp.status_code})"
                overall_success = False
                probes.append(
                    TestLlmProbeResult(
                        label=label,
                        status=status,
                        auth_ok=False,
                        latency_ms=latency_ms,
                        detected_structured_mode="none",
                        supports_tools=False,
                        has_usage=False,
                        has_reasoning_tags=False,
                        message=message,
                    )
                )
                continue
            elif resp.status_code == 429:
                status = "rate_limited"
                message = "Rate limited (HTTP 429)"
                probes.append(
                    TestLlmProbeResult(
                        label=label,
                        status=status,
                        auth_ok=True,
                        latency_ms=latency_ms,
                        detected_structured_mode="unknown",
                        supports_tools=False,
                        has_usage=False,
                        has_reasoning_tags=False,
                        message=message,
                    )
                )
                continue
            else:
                status = "error"
                message = f"HTTP {resp.status_code}: {resp.text[:100]}"
                probes.append(
                    TestLlmProbeResult(
                        label=label,
                        status=status,
                        auth_ok=False,
                        latency_ms=latency_ms,
                        detected_structured_mode="none",
                        supports_tools=False,
                        has_usage=False,
                        has_reasoning_tags=False,
                        message=message,
                    )
                )
                continue

        except Exception as e:
            probes.append(
                TestLlmProbeResult(
                    label=label,
                    status="error",
                    auth_ok=False,
                    latency_ms=int((time.time() - start_t) * 1000),
                    detected_structured_mode="none",
                    supports_tools=False,
                    has_usage=False,
                    has_reasoning_tags=False,
                    message=str(e),
                )
            )
            continue

        # 2. Probe Structured Outputs Ladder
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "required": ["status"],
            "additionalProperties": False,
        }
        # Try strict: true
        try:
            with httpx.Client(timeout=15.0) as client:
                resp_strict = client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {"name": "test", "strict": True, "schema": schema},
                        },
                        "max_tokens": 20,
                    },
                    headers=headers,
                )
            if resp_strict.status_code == 200:
                detected_mode = "strict_schema"
            else:
                # Try strict: false (best_effort_schema)
                with httpx.Client(timeout=15.0) as client:
                    resp_best = client.post(
                        f"{base_url}/chat/completions",
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {"name": "test", "strict": False, "schema": schema},
                            },
                            "max_tokens": 20,
                        },
                        headers=headers,
                    )
                if resp_best.status_code == 200:
                    detected_mode = "best_effort_schema"
                else:
                    # Try json_object
                    with httpx.Client(timeout=15.0) as client:
                        resp_obj = client.post(
                            f"{base_url}/chat/completions",
                            json={
                                "model": model,
                                "messages": [{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
                                "response_format": {"type": "json_object"},
                                "max_tokens": 20,
                            },
                            headers=headers,
                        )
                    if resp_obj.status_code == 200:
                        detected_mode = "json_object"
                    else:
                        detected_mode = "prompt_only"
        except Exception:
            detected_mode = "prompt_only"

        # 3. Probe Tools
        tool_spec = [
            {
                "type": "function",
                "function": {
                    "name": "ping_tool",
                    "description": "A ping test tool",
                    "parameters": {"type": "object", "properties": {"val": {"type": "string"}}},
                },
            }
        ]
        try:
            with httpx.Client(timeout=15.0) as client:
                resp_tool = client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Call ping_tool with val=hello"}],
                        "tools": tool_spec,
                        "max_tokens": 50,
                    },
                    headers=headers,
                )
            if resp_tool.status_code == 200:
                supports_tools = True
        except Exception:
            supports_tools = False

        probes.append(
            TestLlmProbeResult(
                label=label,
                status="ok",
                auth_ok=True,
                latency_ms=latency_ms,
                detected_structured_mode=detected_mode,
                supports_tools=supports_tools,
                has_usage=has_usage,
                has_reasoning_tags=has_reasoning,
                message="Probe passed successfully",
            )
        )

    return TestLlmResponse(success=overall_success, probes=probes)
