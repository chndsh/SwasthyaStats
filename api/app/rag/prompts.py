"""Prompt templates and tool schemas for RAG orchestrator."""
from typing import List, Dict, Any

SYSTEM_PROMPT = """You are a helpful and meticulous health records assistant.
Your job is to answer user questions about their health records, lab reports, and medical history using ONLY the retrieved information provided to you.

Rules:
1. Base your answer strictly and exclusively on the tool results provided. Do not extrapolate, assume, or invent facts.
2. If the tool results do not contain the answer, or no relevant data was found, reply: "I couldn't find that in your records."
3. When referencing observations or facts, ALWAYS include citation tags inline:
   - For a specific lab observation: [obs:ID] (where ID is the integer id of the observation)
   - For general document/report text: [doc:ID p:N] (where ID is the document_id and N is the page number)
4. Never provide medical advice, diagnosis, treatment plans, or medication dosage adjustments. You only summarize and quote existing health records.
5. Keep answers direct, objective, and clear.
"""

ROUTER_SYSTEM_PROMPT = """You are a health records query router. Given a user question, decide which tool to call to retrieve relevant data.
Available tools:
- get_observations: retrieve confirmed observations for a test (args: {"test": "test_name", "from_date"?: "YYYY-MM-DD", "to_date"?: "YYYY-MM-DD"})
- get_latest_observations: retrieve latest observations for multiple tests (args: {"tests": ["test1", "test2"]})
- list_tests: list all available lab tests (args: {})
- search_documents: hybrid semantic/keyword search over document notes, medications, prescriptions (args: {"query": "search query", "top_k"?: 5})

Output ONLY valid JSON in this format:
{"tool": "<tool_name>", "args": {<arguments>}}
If no tool is relevant, output:
{"tool": "none", "args": {}}
"""


def get_tool_specs() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_observations",
                "description": "Get confirmed numerical/text observations for a given lab test name or alias over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test": {
                            "type": "string",
                            "description": "Name or abbreviation of the lab test, e.g. 'HbA1c', 'Hemoglobin', 'TSH'.",
                        },
                        "from_date": {
                            "type": "string",
                            "description": "Optional ISO start date YYYY-MM-DD.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "Optional ISO end date YYYY-MM-DD.",
                        },
                    },
                    "required": ["test"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_latest_observations",
                "description": "Get the most recent observation for one or more lab tests.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tests": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of test names to look up.",
                        },
                    },
                    "required": ["tests"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_tests",
                "description": "List all lab tests recorded in the patient records, along with count and latest date.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Semantic and keyword search over document text, clinic notes, medications, and general report contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or question terms.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of chunks to return (default 5).",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]
