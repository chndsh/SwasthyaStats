"""RAG orchestrator: manages tool-calling loop (native or router fallback) and citation parsing."""
from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.schemas import CitationRef
from app.services.settings import SettingsService
from app.llm.client import OpenAICompatClient
from app.rag.prompts import SYSTEM_PROMPT, ROUTER_SYSTEM_PROMPT, get_tool_specs
from app.rag.tools import (
    get_observations,
    get_latest_observations,
    list_tests,
    search_documents,
)

logger = logging.getLogger(__name__)

OBS_CITATION_REGEX = re.compile(r"\[obs:(\d+)\]")
DOC_CITATION_REGEX = re.compile(r"\[doc:(\d+)(?:\s+p:(\d+))?\]")


@dataclass
class AskResult:
    answer: str
    citations: List[CitationRef]


def parse_citations(text: str) -> List[CitationRef]:
    """Extract unique [obs:ID] and [doc:ID p:N] citations from text preserving order."""
    seen = set()
    citations: List[CitationRef] = []

    # Find [obs:ID]
    for match in OBS_CITATION_REGEX.finditer(text):
        obs_id = int(match.group(1))
        key = ("obs", obs_id, None)
        if key not in seen:
            seen.add(key)
            citations.append(CitationRef(type="obs", id=obs_id, page=None))

    # Find [doc:ID p:N]
    for match in DOC_CITATION_REGEX.finditer(text):
        doc_id = int(match.group(1))
        page_no = int(match.group(2)) if match.group(2) else None
        key = ("doc", doc_id, page_no)
        if key not in seen:
            seen.add(key)
            citations.append(CitationRef(type="doc", id=doc_id, page=page_no))

    return citations


def execute_tool(db: Session, tool_name: str, args: Dict[str, Any]) -> Any:
    """Safely dispatch tool by name."""
    if tool_name == "get_observations":
        test = args.get("test", "")
        from_str = args.get("from_date")
        to_str = args.get("to_date")
        from_d = date.fromisoformat(from_str) if from_str else None
        to_d = date.fromisoformat(to_str) if to_str else None
        return get_observations(db, test, from_date=from_d, to_date=to_d)

    elif tool_name == "get_latest_observations":
        tests = args.get("tests", [])
        if isinstance(tests, str):
            tests = [tests]
        return get_latest_observations(db, tests)

    elif tool_name == "list_tests":
        return list_tests(db)

    elif tool_name == "search_documents":
        query = args.get("query", "")
        top_k = int(args.get("top_k", 5))
        return search_documents(db, query, top_k=top_k)

    logger.warning(f"Unknown tool called: {tool_name}")
    return {"error": f"Unknown tool: {tool_name}"}


def ask(db: Session, question: str) -> AskResult:
    """Orchestrate RAG answer generation using native tool calling or router fallback."""
    settings_service = SettingsService(db)
    settings = settings_service.get_read_settings()
    llm = OpenAICompatClient(db)

    supports_tools = getattr(settings, "llm_supports_tools", True)
    tool_specs = get_tool_specs()

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    if supports_tools:
        # Native Tool Calling Loop (max 3 rounds)
        for _ in range(3):
            resp = llm.chat(
                messages=messages,
                purpose="route",
                tools=tool_specs,
                temperature=0.0,
            )

            if not resp.tool_calls:
                # LLM chose not to call any more tools
                if resp.content:
                    # If it already provided an answer directly
                    citations = parse_citations(resp.content)
                    return AskResult(answer=resp.content, citations=citations)
                break

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": resp.content or "",
                "tool_calls": resp.tool_calls,
            })

            # Execute all tool calls
            for tc in resp.tool_calls:
                fn_name = tc.get("function", {}).get("name", "")
                fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except Exception:
                    fn_args = {}

                tool_result = execute_tool(db, fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", "call_default"),
                    "content": json.dumps(tool_result, default=str),
                })

    else:
        # Router-prompt Fallback
        router_messages = [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        router_resp = llm.chat(
            messages=router_messages,
            purpose="route",
            temperature=0.0,
        )

        try:
            # Strip markdown fences if present
            cleaned_json = router_resp.content.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.split("\n", 1)[1]
                if cleaned_json.endswith("```"):
                    cleaned_json = cleaned_json.rsplit("```", 1)[0]
            parsed = json.loads(cleaned_json)
            tool_name = parsed.get("tool", "none")
            tool_args = parsed.get("args", {})
        except Exception as e:
            logger.warning(f"Failed to parse router output: {e}, text: {router_resp.content}")
            tool_name = "none"
            tool_args = {}

        if tool_name != "none":
            tool_result = execute_tool(db, tool_name, tool_args)
            messages.append({
                "role": "system",
                "content": f"Tool '{tool_name}' returned: {json.dumps(tool_result, default=str)}",
            })

    # Final Answer Synthesis (no tools, no json_schema constraint)
    answer_resp = llm.chat(
        messages=messages,
        purpose="answer",
        temperature=0.0,
    )

    answer_text = answer_resp.content or "I couldn't find that in your records."
    citations = parse_citations(answer_text)

    return AskResult(answer=answer_text, citations=citations)
