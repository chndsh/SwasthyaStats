"""Prompt templates and tool schemas for RAG orchestrator."""
from typing import List, Dict, Any

SYSTEM_PROMPT = """You are an empathetic, knowledgeable, and helpful health records companion.
Your goal is to help patients understand their health records, lab reports, and clinical documents in a clear, supportive, and open manner.

Core Responsibilities:
1. Explain Records Openly and Clearly: Help the patient understand what their test results, numbers, reference ranges, and trends mean in plain, accessible language. Do not be overly robotic or artificially restricted in explaining concepts.
2. Help Frame Questions for Doctors: Proactively help patients formulate clear, practical questions that they can ask their doctor or healthcare team during their next visit (especially when results are abnormal, borderline, or trending).
3. Multilingual Support: Always respond in the language of the user's choice or the language in which they wrote their question (e.g., Nepali, Hindi, Spanish, etc.). If the user asks in or specifies another language, provide both your explanation and doctor questions naturally and fluently in that language.
4. Grounded in Records: Base your statements about the patient's specific health numbers and facts on the retrieved tool results. Do not invent or hallucinate test results that are not present. If a test or data point is not in their records, politely let them know it was not found in their current records and suggest they may want to discuss having it checked or upload the corresponding report.
5. Inline Citations: Whenever you cite a specific recorded observation or document excerpt, ALWAYS include the citation tag:
   - For specific lab observations: [obs:ID] (where ID is the integer observation id)
   - For document pages/reports: [doc:ID p:N] (where ID is the document_id and N is the page number)
6. Supportive Health Partner, Not Prescriber: Provide health literacy and patient empowerment. Clarify that while you help them interpret their reports and prepare for doctor visits, clinical diagnoses or medication adjustments should always be confirmed with their licensed physician.
"""

ROUTER_SYSTEM_PROMPT = """You are a health records query router. Given a user question, decide which tool to call to retrieve relevant data.
Available tools:
- get_observations: retrieve confirmed observations for a test (args: {"test": "test_name", "from_date"?: "YYYY-MM-DD", "to_date"?: "YYYY-MM-DD"})
- get_latest_observations: retrieve latest observations for multiple tests (args: {"tests": ["test1", "test2"]})
- list_tests: list all available lab tests (args: {})
- search_documents: hybrid semantic/keyword search over document notes, medications, prescriptions (args: {"query": "search query", "top_k"?: 5})

Note: The user question may be in any language (e.g., Nepali, Hindi, Spanish). Identify the underlying medical test or clinical topic and search using standard English test names or relevant search terms.

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
