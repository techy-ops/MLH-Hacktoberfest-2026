"""
Gemma 4 via Gemini API — Tool-Selection Intelligence Layer
============================================================
Uses the current official Google Gen AI Python SDK: google-genai
  pip install google-genai

SDK import pattern:
  from google import genai
  from google.genai import types
  client = genai.Client(api_key=...)

This service acts EXCLUSIVELY as a ROUTER.
  - It understands the user's text (and optional image).
  - It selects the most appropriate existing PayprAPI tool.
  - It NEVER executes a tool itself.

Output contract:
  {
    "tool":      "<one of REGISTERED_TOOLS keys>",
    "arguments": { ... },
    "reason":    "..."
  }
"""
import os
import json
import logging
import asyncio
from typing import Optional

logger = logging.getLogger("marketplace.gemma")

# ── Registered PayprAPI tools ─────────────────────────────────────────────────
# Single source of truth — keys MUST match the existing AI-service router IDs.
REGISTERED_TOOLS: dict[str, dict] = {
    "translate": {
        "description": (
            "Translate text from one natural language to another. "
            "Use when the user wants to convert text to a different language."
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
            "Use when the user wants a brief overview, summary, or digest of content."
        ),
        "endpoint": "/api/summarize",
        "required_arguments": ["text"],
        "optional_arguments": ["max_sentences", "style"],
        "argument_hints": {
            "text": "The full text to summarize (50-10000 characters).",
            "max_sentences": "Maximum summary sentences (1-10, default 3).",
            "style": "Summary style: 'concise' | 'detailed' | 'bullet' (default 'concise').",
        },
    },
    "sentiment": {
        "description": (
            "Analyze the emotional tone and sentiment of text. "
            "Use when the user wants to know if text is positive, negative, or neutral, "
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
            "Use when the user wants to create, generate, draw, or render an image. "
            "Also use when an uploaded image is provided and the user wants a new image "
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

_ALLOWED_TOOL_NAMES = set(REGISTERED_TOOLS.keys())

# ── System prompt ─────────────────────────────────────────────────────────────
_TOOL_CATALOG = "\n".join(
    f'- "{name}": {cfg["description"]}  Required args: {cfg["required_arguments"]}'
    for name, cfg in REGISTERED_TOOLS.items()
)

SYSTEM_PROMPT = f"""You are the PayprAPI Tool Router.

Your ONLY job is to analyse what the user wants and select the single most
appropriate tool from the PayprAPI tool registry listed below.
You are a router -- you NEVER execute a tool or produce the final result yourself.

AVAILABLE TOOLS:
{_TOOL_CATALOG}

RULES:
1. Respond with ONLY valid JSON -- no markdown fences, no prose, no extra text.
2. The "tool" field MUST be exactly one of: {sorted(_ALLOWED_TOOL_NAMES)}.
3. The "arguments" object MUST contain every required argument for the selected tool.
4. If the user provides an image, use its visual content to inform tool selection
   and argument values (e.g. describe the image in "prompt" for image_gen, or
   extract visible text for translate/summarize/sentiment).
5. If the request is ambiguous, pick the closest matching tool and explain in "reason".
6. If no tool fits well, still pick the best candidate and note uncertainty in "reason".
7. NEVER invent a tool name not in the registry above.

STRICT RESPONSE FORMAT (plain JSON, no wrapping):
{{
  "tool": "<tool_name>",
  "arguments": {{ "<arg>": "<value>", ... }},
  "reason": "<one sentence explaining your choice>"
}}
"""

# ── Custom exceptions ─────────────────────────────────────────────────────────

class ConfigurationError(Exception):
    """Raised when required configuration (e.g. API key or SDK) is missing."""


class InvalidModelOutputError(Exception):
    """Raised when Gemma returns output that cannot be safely mapped to a registered tool."""


# ── Supported image MIME types ─────────────────────────────────────────────────
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# ── Client factory ─────────────────────────────────────────────────────────────

def _build_client():
    """
    Build and return a google.genai.Client using GEMINI_API_KEY from env.

    Raises
    ------
    ConfigurationError
        If GEMINI_API_KEY is not set or the google-genai package is not installed.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "GEMINI_API_KEY environment variable is not set. "
            "Obtain a key at https://aistudio.google.com/ and add it to "
            "backend/ai-services/.env"
        )

    try:
        from google import genai  # type: ignore[import]
    except ImportError as exc:
        raise ConfigurationError(
            "google-genai package is not installed. "
            "Run:  pip install google-genai"
        ) from exc

    return genai.Client(api_key=api_key)


def _model_name() -> str:
    """Return the configured Gemma model name (env-configurable, never hardcoded)."""
    return os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")


# ── Public API ────────────────────────────────────────────────────────────────

async def select_tool(
    user_text: str,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
) -> dict:
    """
    Ask Gemma 4 (via Gemini API) to select the appropriate PayprAPI tool.

    Parameters
    ----------
    user_text : str
        The user's natural-language request.
    image_bytes : bytes, optional
        Raw image bytes (JPEG/PNG/WEBP/GIF). If provided, the image is passed
        to the model as a multimodal input Part.
    image_mime : str
        MIME type of the supplied image. Must be in ALLOWED_IMAGE_MIMES.

    Returns
    -------
    dict with keys:
        tool      – name of the selected PayprAPI tool (one of REGISTERED_TOOLS)
        arguments – dict of arguments to pass to that tool endpoint
        reason    – Gemma's one-sentence explanation
        endpoint  – the existing PayprAPI endpoint path (e.g. "/api/summarize")

    Raises
    ------
    ConfigurationError      – API key missing or SDK not installed.
    InvalidModelOutputError – Gemma returned unrecognised / incomplete output.
    RuntimeError            – Gemini API network/server failure.
    ValueError              – Invalid image MIME type supplied by the caller.
    """
    from google.genai import types  # type: ignore[import]

    # ── Validate image MIME early (before calling the API) ────────────────────
    if image_bytes is not None:
        if image_mime not in ALLOWED_IMAGE_MIMES:
            raise ValueError(
                f"Unsupported image MIME type '{image_mime}'. "
                f"Supported: {sorted(ALLOWED_IMAGE_MIMES)}"
            )
        if len(image_bytes) == 0:
            raise ValueError("image_bytes must not be empty.")

    client = _build_client()
    model = _model_name()

    # ── Build content parts ───────────────────────────────────────────────────
    if image_bytes is not None:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
            user_text,
        ]
        logger.info(
            "[Gemma] Multimodal request | model=%s | image=%s size=%d bytes | "
            "text_len=%d",
            model, image_mime, len(image_bytes), len(user_text),
        )
    else:
        contents = [user_text]
        logger.info(
            "[Gemma] Text-only request | model=%s | text_len=%d",
            model, len(user_text),
        )

    # ── Build generation config with system instruction ───────────────────────
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        # Ask for a deterministic, short structured response
        temperature=0.0,
        max_output_tokens=512,
    )

    # ── Call Gemini API (async path via client.aio) ───────────────────────────
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
    except Exception as exc:
        # Surface model-not-found or auth errors clearly
        err_str = str(exc)
        if "not found" in err_str.lower() or "invalid" in err_str.lower() and "model" in err_str.lower():
            logger.error("[Gemma] Model not available: model=%s error=%s", model, exc)
            raise RuntimeError(
                f"Gemma model '{model}' is not available via this Gemini API key. "
                f"Check https://aistudio.google.com/ to confirm the model ID. "
                f"Original error: {exc}"
            ) from exc
        logger.error("[Gemma] Gemini API error: %s", exc)
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    raw_text = response.text
    if not raw_text:
        raise InvalidModelOutputError(
            f"Gemma returned an empty response for model '{model}'. "
            "The model may not support this request type."
        )

    raw_text = raw_text.strip()
    logger.debug("[Gemma] Raw output: %s", raw_text[:500])

    return _parse_and_validate(raw_text)


def _parse_and_validate(raw_text: str) -> dict:
    """
    Parse Gemma's JSON output and validate against the registered tool registry.

    Raises InvalidModelOutputError on any validation failure so the caller
    can return a clean 503 without executing any tool.
    """
    text = raw_text.strip()

    # Strip markdown code fences if the model adds them despite instructions
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]  # drop opening ``` or ```json
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop closing ```
        text = "\n".join(lines).strip()

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutputError(
            f"Gemma returned non-JSON output. "
            f"Cannot safely execute any tool. Raw snippet: {raw_text[:300]!r}"
        ) from exc

    if not isinstance(data, dict):
        raise InvalidModelOutputError(
            f"Gemma output is not a JSON object (got {type(data).__name__}). "
            f"Raw: {raw_text[:300]!r}"
        )

    # Validate tool name against the strict registry whitelist
    tool_name = data.get("tool")
    if tool_name not in _ALLOWED_TOOL_NAMES:
        raise InvalidModelOutputError(
            f"Gemma returned unrecognised tool name '{tool_name}'. "
            f"Allowed: {sorted(_ALLOWED_TOOL_NAMES)}. "
            f"Raw: {raw_text[:300]!r}"
        )

    # Validate arguments dict
    arguments = data.get("arguments")
    if not isinstance(arguments, dict):
        raise InvalidModelOutputError(
            f"Gemma output for tool '{tool_name}' has no valid 'arguments' dict. "
            f"Raw: {raw_text[:300]!r}"
        )

    # Verify all required arguments are present and non-empty
    tool_cfg = REGISTERED_TOOLS[tool_name]
    missing = [
        arg for arg in tool_cfg["required_arguments"]
        if not arguments.get(arg, "")
    ]
    if missing:
        raise InvalidModelOutputError(
            f"Gemma's output for tool '{tool_name}' is missing required "
            f"arguments: {missing}. Raw: {raw_text[:300]!r}"
        )

    reason = str(data.get("reason", "")).strip()

    logger.info(
        "[Gemma] Tool selected: '%s' | reason: %s | args_keys: %s",
        tool_name, reason, list(arguments.keys()),
    )

    return {
        "tool": tool_name,
        "arguments": arguments,
        "reason": reason,
        "endpoint": tool_cfg["endpoint"],
    }


# ── Model availability probe (optional startup check) ─────────────────────────

async def probe_model_availability() -> dict:
    """
    Send a minimal request to verify the configured model is reachable.
    Returns {"available": True, "model": "..."} or raises RuntimeError.

    Call this from a startup event or a health-check endpoint if needed.
    This does NOT substitute the model silently; it raises explicitly on failure.
    """
    from google.genai import types  # type: ignore[import]

    client = _build_client()
    model = _model_name()

    logger.info("[Gemma] Probing model availability: %s", model)

    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=["Reply with the single word: ready"],
            config=types.GenerateContentConfig(
                max_output_tokens=8,
                temperature=0.0,
            ),
        )
        text = (response.text or "").strip().lower()
        logger.info("[Gemma] Model probe response: %r", text)
        return {"available": True, "model": model, "probe_response": text}
    except Exception as exc:
        logger.error("[Gemma] Model probe FAILED for '%s': %s", model, exc)
        raise RuntimeError(
            f"Gemma model '{model}' is NOT reachable via the configured GEMINI_API_KEY. "
            f"Error: {exc}"
        ) from exc
