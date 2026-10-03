"""
Agent Router — /api/agent
=========================
Provides a single endpoint:

  POST /api/agent/select-tool
    - Accepts user text (and optional image upload)
    - Calls Gemma 4 via the Gemini API to select the appropriate PayprAPI tool
    - Returns structured tool selection: { tool, arguments, reason, endpoint }
    - Does NOT execute the tool (that remains the existing tool endpoint's job)
    - Does NOT require X402 payment (it is a routing helper, not a billable AI tool)

The caller (e.g. the Agent Console) is responsible for:
  1. Reading the returned endpoint + arguments
  2. Sending a payment via /payment/send
  3. Calling the actual AI endpoint through the Gateway's X402 flow
"""
import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from services.gemma import (
    select_tool,
    REGISTERED_TOOLS,
    ConfigurationError,
    InvalidModelOutputError,
)

logger = logging.getLogger("marketplace.agent")
router = APIRouter()

# Maximum image upload size: 10 MB
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Allowed image MIME types
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/select-tool")
async def agent_select_tool(
    prompt: str = Form(..., description="User's natural-language request"),
    image: Optional[UploadFile] = File(None, description="Optional image upload (JPEG/PNG/WEBP/GIF)"),
):
    """
    Use Gemma 4 (via the Gemini API) to select the best existing PayprAPI tool
    for a given user request (text + optional image).

    Returns
    -------
    JSON object:
      {
        "tool": "<tool_id>",
        "arguments": { ... },
        "reason": "...",
        "endpoint": "/api/<tool_path>"
      }

    Error responses
    ---------------
    400 – Invalid/unsupported image input
    422 – Missing required fields
    500 – GEMINI_API_KEY not configured / Gemini API failure
    503 – Gemma returned an unrecognised tool or malformed output
    """
    image_bytes: Optional[bytes] = None
    image_mime: str = "image/jpeg"

    # ── Image handling ────────────────────────────────────────────────────────
    if image is not None:
        # Validate MIME type before reading the body
        content_type = (image.content_type or "").lower().split(";")[0].strip()
        if content_type not in ALLOWED_MIMES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Unsupported image type",
                    "received": content_type,
                    "supported": sorted(ALLOWED_MIMES),
                },
            )
        image_mime = content_type

        # Read and size-check the image
        raw = await image.read()
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Image too large",
                    "max_bytes": MAX_IMAGE_BYTES,
                    "received_bytes": len(raw),
                },
            )
        if len(raw) == 0:
            raise HTTPException(
                status_code=400,
                detail={"error": "Uploaded image file is empty"},
            )
        image_bytes = raw
        logger.info(
            f"[Agent] Image received: mime={image_mime}, size={len(image_bytes)} bytes"
        )

    # ── Validate prompt ───────────────────────────────────────────────────────
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=422,
            detail={"error": "prompt must not be empty"},
        )

    logger.info(
        f"[Agent] select-tool called | prompt_len={len(prompt)} "
        f"| has_image={image_bytes is not None}"
    )

    # ── Call Gemma 4 ──────────────────────────────────────────────────────────
    try:
        result = await select_tool(
            user_text=prompt,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
    except ConfigurationError as exc:
        logger.error(f"[Agent] Configuration error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Gemma not configured",
                "detail": str(exc),
            },
        )
    except InvalidModelOutputError as exc:
        logger.warning(f"[Agent] Invalid model output: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Gemma returned an unrecognised response",
                "detail": str(exc),
            },
        )
    except RuntimeError as exc:
        logger.error(f"[Agent] Runtime error: {exc}")
        return JSONResponse(
            status_code=502,
            content={
                "error": "Gemini API request failed",
                "detail": str(exc),
            },
        )
    except Exception as exc:
        logger.exception(f"[Agent] Unexpected error in select_tool: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal agent error",
                "detail": str(exc),
            },
        )

    return result


@router.get("/tools")
async def list_tools():
    """
    Return the registry of tools that Gemma may select from.
    Useful for the frontend to display available options.
    """
    return {
        "tools": [
            {
                "id": name,
                "description": cfg["description"],
                "endpoint": cfg["endpoint"],
                "required_arguments": cfg["required_arguments"],
                "optional_arguments": cfg["optional_arguments"],
            }
            for name, cfg in REGISTERED_TOOLS.items()
        ],
        "total": len(REGISTERED_TOOLS),
    }
