"""
Uses the Google Gemini API to analyse a document and extract a reusable template.

Output contract
───────────────
The LLM is instructed to return ONLY a JSON object matching ExtractionResult.
We validate aggressively and never silently swallow parse failures.
"""
import json
import re
import os
from typing import Any

# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import errors as genai_errors
# pyrefly: ignore [missing-import]
from google.genai import types as genai_types

from app.models.mapping import ENTITY_SCHEMA


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


EXTRACTION_SYSTEM_PROMPT = """You are an expert legal and transactional document analyst.
Your job is to analyse a document and produce a structured, reusable template.

You MUST respond with ONLY valid JSON — no markdown fences, no explanation, no preamble.
The JSON must match this exact schema:

{
  "document_type": "<contract|agreement|allotment|invoice|general>",
  "template_name": "<short descriptive name>",
  "description": "<one-sentence description of what this document is>",
  "issuing_party": "<Name of the company or party that created/issued this document>",
  "fields": [
    {
      "key": "FIELD_KEY_IN_SCREAMING_SNAKE_CASE",
      "label": "Human Readable Label",
      "description": "What this field represents",
      "field_type": "<text|date|currency|number|address|identifier>",
      "example_value": "The actual value found in the original document",
      "required": true,
      "is_author_field": false
    }
  ],
  "template_body": "The full document text with every dynamic value replaced by {{FIELD_KEY}} placeholders. Preserve all formatting, numbering, and structure.",
  "warnings": ["Any issues or ambiguities noticed during extraction"]
}

Rules:
1. Every value that could differ between transactions MUST become a {{FIELD_KEY}} placeholder.
2. Field keys must be SCREAMING_SNAKE_CASE and globally unique within the document.
3. Do NOT leave any names, dates, amounts, IDs, addresses, or identifiers as literals in template_body.
4. If a value appears multiple times, use the SAME placeholder key every time.
5. warnings is mandatory — use an empty list [] if there are none.
6. Respond with ONLY the JSON object. No markdown. No prose.
7. CRITICAL — Set "is_author_field": true for fields that belong to the ISSUING/AUTHOR party of
   this document (e.g. the company whose letterhead or template this is). These are fields whose
   values are already known and fixed in the document (e.g. the issuing company's own signer name,
   title, signature block, registration number). Set "is_author_field": false for fields that
   belong to the OTHER/COUNTER party and must be supplied at generation time.
8. For every author field, example_value MUST contain the EXACT value as it appears in the document.
   These will be auto-filled — do not leave example_value blank for author fields.
9. For contracts and agreements, you MUST always extract signature-related fields for BOTH the issuing party and the counterparty, even if they are blank or lines in the original text (e.g. COUNTERPARTY_SIGNER_NAME, COUNTERPARTY_SIGNER_TITLE, etc.). If there is a human signature or a printed name (e.g. "Jay K" or similar) present in the signature block of the original document, you MUST extract that name/title and set it as the example_value for the counterparty as well. This allows the system to auto-populate them as defaults while still allowing overrides.
"""

ENTITY_CONTEXT = """
Available data entities and their attributes for mapping guidance:
""" + json.dumps(
    {
        entity: {
            "label": data["label"],
            "attributes": list(data["attributes"].keys()),
        }
        for entity, data in ENTITY_SCHEMA.items()
    },
    indent=2,
)


class AIExtractionError(Exception):
    """Raised when AI extraction fails or returns unparseable output."""

    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


def _clean_json_response(raw: str) -> str:
    """Strip markdown fences if the model accidentally included them."""
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    return cleaned.strip()


def _validate_extraction(data: dict) -> list[str]:
    """Return list of validation error strings (empty = valid)."""
    errors = []
    required_keys = ["document_type", "template_name", "description", "fields", "template_body", "warnings"]
    for k in required_keys:
        if k not in data:
            errors.append(f"Missing required key: '{k}'")

    if "fields" in data:
        if not isinstance(data["fields"], list):
            errors.append("'fields' must be a list")
        else:
            for i, f in enumerate(data["fields"]):
                for fk in ["key", "label", "description", "field_type", "example_value"]:
                    if fk not in f:
                        errors.append(f"Field[{i}] missing '{fk}'")

    if "template_body" in data and "fields" in data:
        if isinstance(data["fields"], list):
            for f in data["fields"]:
                key = f.get("key", "")
                if key and f"{{{{key}}}}" not in data["template_body"]:
                    # Check without escaped braces
                    if "{{" + key + "}}" not in data["template_body"]:
                        errors.append(
                            f"Field key '{key}' has no placeholder in template_body"
                        )

    return errors


def _try_recover_truncated_json(raw: str) -> str | None:
    """
    Attempt to repair a JSON string that was cut off mid-generation.
    Closes any open string, array and object in reverse order.
    Returns repaired string, or None if unrecoverable.
    """
    text = raw.strip()
    # Track open brackets/braces
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

    if not stack and not in_string:
        return text  # already valid

    repair = text
    # Close open string if any
    if in_string:
        repair += '"'
    # Close open structures in reverse
    for ch in reversed(stack):
        repair += '}' if ch == '{' else ']'
    return repair


def extract_template_with_ai(document_text: str) -> dict[str, Any]:
    """
    Call Gemini to extract a template from document text.

    Returns validated extraction dict.
    Raises AIExtractionError on any failure — never silently fails.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise AIExtractionError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    # Smart truncation: take the start of the document + the end (where signatures live).
    # This ensures the AI always sees the signing/AGREED section even in long docs.
    head_chars = 8000
    tail_chars = 4000
    if len(document_text) <= head_chars + tail_chars:
        truncated_input = document_text
    else:
        head = document_text[:head_chars]
        tail = document_text[-tail_chars:]
        truncated_input = head + "\n\n[... middle section truncated for brevity ...]\n\n" + tail

    user_message = f"""Analyse this document and extract a reusable template.

{ENTITY_CONTEXT}

DOCUMENT TEXT:
{truncated_input}
"""

    last_error: Exception | None = None

    # Retry up to 2 times (first with 65k tokens, second with 32k as fallback)
    for max_tokens in (65536, 32768):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=genai_types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                    temperature=0.2,
                ),
            )
        except genai_errors.APIError as e:
            raise AIExtractionError(f"Gemini API error: {str(e)}") from e
        except Exception as e:
            raise AIExtractionError(f"Unexpected error calling Gemini API: {str(e)}") from e

        raw_text = response.text or ""

        if not raw_text.strip():
            last_error = AIExtractionError("AI returned an empty response.", raw_response=raw_text)
            continue

        cleaned = _clean_json_response(raw_text)

        # First, try parsing as-is
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # The response may have been truncated — try to repair it
            repaired = _try_recover_truncated_json(cleaned)
            if repaired:
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError as e2:
                    last_error = AIExtractionError(
                        f"AI response is not valid JSON (even after repair): {str(e2)}",
                        raw_response=raw_text,
                    )
                    continue
            else:
                last_error = AIExtractionError(
                    "AI response is not valid JSON and could not be repaired.",
                    raw_response=raw_text,
                )
                continue

        if not isinstance(data, dict):
            last_error = AIExtractionError(
                "AI response parsed but is not a JSON object.",
                raw_response=raw_text,
            )
            continue

        # Success — enrich with warnings
        validation_errors = _validate_extraction(data)
        if validation_errors:
            existing_warnings = data.get("warnings", [])
            data["warnings"] = existing_warnings + [
                f"[VALIDATION] {e}" for e in validation_errors
            ]

        if "warnings" not in data:
            data["warnings"] = []

        return data

    # All retries failed
    raise last_error or AIExtractionError("AI extraction failed after retries.")