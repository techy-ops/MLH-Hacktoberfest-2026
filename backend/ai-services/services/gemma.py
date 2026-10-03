"""
Gemma 4 via Gemini API — Tool-Selection Intelligence Layer
============================================================
This service acts exclusively as a ROUTER.  It understands the user's
text (and optional image) and selects the most appropriate existing
PayprAPI tool.  It never executes a tool itself.

The structured output it returns is:
  {
    "tool": "<one of the REGISTERED_TOOLS keys>",
    "arguments": { ... },
    "reason": "..."
  }
"""
import os
import json
import base64
import logging
from typing import Optional

logger = logging.getLogger("marketplace.gemma")

# ── Registered PayprAPI tools ─────────────────────────────────────────────────
# This is the single source of truth for which tools Gemma may select.
# Keys MUST match the endpoint IDs used by the existing AI-services routers.
REGISTERED_TOOLS: dict[str, dict] = {
    "translate": {
        "description": (
            "Translate text from one natural language to another. "
            "Use this when the user wants to convert text to a different language."
        ),
        "endpoint": "/api/translate",
        "required_arguments": ["text", "target_lang"],
        "optional_arguments": ["source_lang"],
        "argument_hints": {
            "text": "The text to translate.",
            "target_lang": "BCP-47 language code for the target language (e.g. 'es', 'fr', 'de').",
            "source_lang": "BCP-47 source language code, or 'auto' to detect automatically.",
        },
    },
    "summarize": {
        "description": (
            "Summarize a long piece of text into a concise, shorter version. "
            "Use this when the user wants a brief overview, summary, or digest of content."
        ),
        "endpoint": "/api/summarize",
        "required_arguments": ["text"],
        "optional_arguments": ["max_sentences", "style"],
        "argument_hints": {
            "text": "The full text to summarize (50-10000 characters).",
            "max_sentences": "Maximum number of sentences in the summary (1-10, default 3).",
            "style": "Summary style: 'concise' | 'detailed' | 'bullet' (default 'concise').",
        },
    },
    "sentiment": {
        "description": (
            "Analyze the emotional tone and sentiment of text. "
            "Use this when the user wants to know if text is positive, negative, or neutral, "
            "or wants emotion/mood analysis."
        ),
        "endpoint": "/api/sentiment",
        "required_arguments": ["text"],
        "optional_arguments": ["granular"],
        "argument_hints": {
            "text": "The text to analyze.",
            "granular": "Return detailed emotion breakdown (true/false, default true).",
        },
    },
    "image_gen": {
        "description": (
            "Generate an AI image from a text prompt. "
            "Use this when the user wants to create, generate, draw, or render an image. "
            "Also use this when an uploaded image is provided and the user wants a new image "
            "inspired by or based on its visual content."
        ),
        "endpoint": "/api/image/generate",
        "required_arguments": ["prompt"],
        "optional_arguments": ["style", "width", "height"],
        "argument_hints": {
            "prompt": "Descriptive text prompt for the image (3-1500 characters).",
            "style": (
                "Art style: 'realistic' | 'anime' | 'digital-art' | 'cinematic' | "
                "'oil-painting' | 'watercolor' | '3d-render' | 'fantasy' | 'pixel-art' | 'sketch'."
            ),
            "width": "Image width in pixels (256-1280, default 1024).",
            "height": "Image height in pixels (256-1280, default 1024).",
        },
    },
}

# ── System prompt ─────────────────────────────────────────────────────────────
_TOOL_CATALOG_TEXT = "\n".join(
    f'- "{name}": {cfg["description"]}  Required args: {cfg["required_arguments"]}'
    for name, cfg in REGISTERED_TOOLS.items()
)

SYSTEM_PROMPT = f"""You are the PayprAPI Tool Router.

Your ONLY job is to analyse what the user wants and select the single most appropriate
tool from the PayprAPI tool registry below.  You are a router -- you NEVER execute
a tool or produce the final result yourself.

AVAILABLE TOOLS:
{_TOOL_CATALOG_TEXT}

RULES:
1. You MUST respond with valid JSON only -- no markdown fences, no extra text.
2. The "tool" field MUST be exactly one of: {list(REGISTERED_TOOLS.keys())}.
3. The "arguments" object MUST include all required arguments for the selected tool.
4. If the user provides an image, use its visual content to inform both tool selection
   and argument values (e.g. describe the image in the prompt for image_gen,
   or extract visible text for translate/summarize/sentiment).
5. If the request is ambiguous but leans toward any of the registered tools, pick the
   closest match and explain your reasoning in the "reason" field.
6. If you cannot confidently map the request to any registered tool, still pick the
   best candidate and note the uncertainty in "reason".
7. You MUST NOT invent tool names that are not in the registry.

RESPONSE FORMAT (strict JSON, no markdown):
{{
  "tool": "<tool_name>",
  "arguments": {{ "<arg>": "<value>", ... }},
  "reason": "<one sentence explaining your choice>"
}}
"""

# ── Custom exceptions ─────────────────────────────────────────────────────────

class ConfigurationError(Exception):
    """Raised when required configuration (e.g. API key) is missing."""


class InvalidModelOutputError(Exception):
    """Raised when Gemma returns output that cannot be mapped to a registered tool."""


# ── Gemini client initialisation ───────────────────────────────────────────────

def _get_client():
    """
    Lazily import and configure the google-generativeai client.
    Raises a clear ConfigurationError if GEMINI_API_KEY is absent.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "GEMINI_API_KEY environment variable is not set. "
            "Add it to your .env file to enable Gemma tool selection."
        )
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise ConfigurationError(
            "google-generativeai package is not installed. "
            "Run: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def select_tool(
    user_text: str,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
) -> dict:
    """
    Ask Gemma 4 to select a PayprAPI tool for the given user request.

    Parameters
    ----------
    user_text : str
        The user's natural-language request.
    image_bytes : bytes, optional
        Raw bytes of an uploaded image (JPEG / PNG / WEBP / GIF).
    image_mime : str
        MIME type of the image, e.g. "image/jpeg".

    Returns
    -------
    dict with keys:
        tool      -- one of the REGISTERED_TOOLS keys
        arguments -- dict of arguments for that tool
        reason    -- Gemma's explanation string
        endpoint  -- the existing PayprAPI endpoint path

    Raises
    ------
    ConfigurationError       -- GEMINI_API_KEY missing or SDK not installed.
    InvalidModelOutputError  -- Gemma returned an unrecognised tool or malformed JSON.
    RuntimeError             -- Gemini API call failed.
    """
    model = _get_client()

    # Build the content parts
    parts: list = [user_text]

    if image_bytes:
        # Validate supported MIME types for Gemma multimodal
        supported_mimes = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if image_mime not in supported_mimes:
            raise InvalidModelOutputError(
                f"Unsupported image MIME type '{image_mime}'. "
                f"Supported: {sorted(supported_mimes)}"
            )
        image_part = {
            "mime_type": image_mime,
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }
        parts = [image_part, user_text]
        logger.info(
            f"[Gemma] Multimodal request: image={image_mime} "
            f"size={len(image_bytes)} bytes, text_len={len(user_text)}"
        )
    else:
        logger.info(f"[Gemma] Text-only request: text_len={len(user_text)}")

    # Call the Gemini API (synchronous SDK call, run in thread pool)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, model.generate_content, parts)
        raw_text: str = response.text.strip()
    except Exception as exc:
        logger.error(f"[Gemma] Gemini API error: {exc}")
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    logger.debug(f"[Gemma] Raw model output: {raw_text}")

    # Parse and validate the JSON response
    return _parse_and_validate(raw_text)


def _parse_and_validate(raw_text: str) -> dict:
    """
    Parse Gemma's JSON output and validate that it references a registered tool.
    Raises InvalidModelOutputError on any validation failure.
    """
    # Strip markdown code fences if the model returns them despite instructions
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # remove closing fence
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutputError(
            f"Gemma returned non-JSON output. Raw: {raw_text[:300]}"
        ) from exc

    if not isinstance(data, dict):
        raise InvalidModelOutputError(
            f"Gemma output is not a JSON object. Raw: {raw_text[:300]}"
        )

    tool_name = data.get("tool")
    if tool_name not in REGISTERED_TOOLS:
        raise InvalidModelOutputError(
            f"Gemma selected unknown tool '{tool_name}'. "
            f"Allowed tools: {list(REGISTERED_TOOLS.keys())}. "
            f"Raw output: {raw_text[:300]}"
        )

    arguments = data.get("arguments")
    if not isinstance(arguments, dict):
        raise InvalidModelOutputError(
            f"Gemma output missing valid 'arguments' dict. Raw: {raw_text[:300]}"
        )

    # Verify all required arguments are present and non-empty
    tool_cfg = REGISTERED_TOOLS[tool_name]
    missing = [a for a in tool_cfg["required_arguments"] if not arguments.get(a)]
    if missing:
        raise InvalidModelOutputError(
            f"Gemma output for tool '{tool_name}' is missing required arguments: {missing}. "
            f"Raw: {raw_text[:300]}"
        )

    reason = data.get("reason", "")
    logger.info(
        f"[Gemma] Tool selected: '{tool_name}' | reason: {reason} | args: {list(arguments.keys())}"
    )

    return {
        "tool": tool_name,
        "arguments": arguments,
        "reason": reason,
        "endpoint": tool_cfg["endpoint"],
    }
