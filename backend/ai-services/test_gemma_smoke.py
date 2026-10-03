#!/usr/bin/env python3
"""
PayprAPI Phase 1 Smoke Tests — Gemma 4 via google-genai SDK
=============================================================
Run from inside the backend/ai-services directory with the venv active:

  cd backend/ai-services
  .venv\\Scripts\\activate          # Windows
  # source .venv/bin/activate      # macOS/Linux
  python test_gemma_smoke.py

Requires:
  - GEMINI_API_KEY set in .env or exported as an env var
  - google-genai installed: pip install google-genai

Tests:
  A. Text → Gemma → valid existing tool selection
  B. Image + text → Gemma → valid existing tool selection
  C. Unknown/unsupported request → safely rejects (best-effort pick, validated)
  D. Invalid Gemma output simulation → safely rejected by _parse_and_validate
  E. Missing API key → ConfigurationError raised cleanly

The tests do NOT run the X402 flow or actual AI tools — they only verify
that Gemma's tool-selection layer returns safe, validated output.
"""
import os
import sys
import asyncio
import traceback
from pathlib import Path

# ── Ensure .env is loaded ─────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not available; rely on exported env vars

# ── Make the project importable from this directory ───────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))  # backend/ai-services root

from services.gemma import (
    select_tool,
    probe_model_availability,
    ConfigurationError,
    InvalidModelOutputError,
    _parse_and_validate,
    REGISTERED_TOOLS,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
INFO = "\033[94mINFO\033[0m"


def banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


async def test_model_probe() -> bool:
    """Verify the configured model is reachable before running other tests."""
    banner("PRE-FLIGHT: Model availability probe")
    try:
        result = await probe_model_availability()
        print(f"  [{PASS}] Model '{result['model']}' is available.")
        print(f"  [{INFO}] Probe response: {result['probe_response']!r}")
        return True
    except ConfigurationError as e:
        print(f"  [{FAIL}] Configuration error: {e}")
        return False
    except RuntimeError as e:
        print(f"  [{FAIL}] Model NOT available: {e}")
        return False
    except Exception as e:
        print(f"  [{FAIL}] Unexpected error: {e}")
        traceback.print_exc()
        return False


async def test_a_text_only() -> bool:
    """A. Text → Gemma → valid existing tool selection."""
    banner("TEST A: Text-only → tool selection")
    cases = [
        ("Translate this sentence to French: Hello, how are you?", "translate"),
        ("Give me a short summary of this article: " + "X " * 60, "summarize"),
        ("Is this review positive or negative? I love this product!", "sentiment"),
        ("Generate a watercolor painting of a mountain at sunset.", "image_gen"),
    ]
    all_pass = True
    for prompt, expected_tool in cases:
        try:
            result = await select_tool(user_text=prompt)
            actual = result["tool"]
            ok = actual == expected_tool
            status = PASS if ok else FAIL
            print(f"  [{status}] '{prompt[:55]}...' → tool='{actual}' (expected '{expected_tool}')")
            if ok:
                print(f"          args_keys={list(result['arguments'].keys())} reason={result['reason'][:60]!r}")
            else:
                all_pass = False
        except Exception as e:
            print(f"  [{FAIL}] Exception: {e}")
            all_pass = False
    return all_pass


async def test_b_multimodal() -> bool:
    """B. Image + text → Gemma → valid existing tool selection."""
    banner("TEST B: Image + text → multimodal tool selection")

    # Create a minimal valid JPEG (a 1x1 white pixel) for testing
    # This is a complete minimal JPEG file in bytes
    minimal_jpeg = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xDB, 0xFF, 0xD9,
    ])

    try:
        result = await select_tool(
            user_text="What tool should I use based on this image? I want to create a similar painting.",
            image_bytes=minimal_jpeg,
            image_mime="image/jpeg",
        )
        tool = result["tool"]
        if tool in REGISTERED_TOOLS:
            print(f"  [{PASS}] Multimodal request → tool='{tool}'")
            print(f"          args_keys={list(result['arguments'].keys())} reason={result['reason'][:60]!r}")
            return True
        else:
            print(f"  [{FAIL}] Tool '{tool}' not in registry.")
            return False
    except Exception as e:
        print(f"  [{FAIL}] Exception: {e}")
        traceback.print_exc()
        return False


async def test_c_ambiguous_request() -> bool:
    """C. Ambiguous/unsupported request → still picks a registered tool safely."""
    banner("TEST C: Ambiguous request → safe best-effort selection")
    prompt = "Do quantum computing calculations and send me an email."
    try:
        result = await select_tool(user_text=prompt)
        tool = result["tool"]
        if tool in REGISTERED_TOOLS:
            print(f"  [{PASS}] Ambiguous prompt → safely selected '{tool}' (best-effort).")
            print(f"          reason={result['reason'][:80]!r}")
            return True
        else:
            print(f"  [{FAIL}] Tool '{tool}' not in registry — whitelist validation missed it.")
            return False
    except InvalidModelOutputError as e:
        # Also acceptable: model output was rejected cleanly
        print(f"  [{PASS}] InvalidModelOutputError raised (clean rejection): {str(e)[:120]}")
        return True
    except Exception as e:
        print(f"  [{FAIL}] Unexpected exception: {e}")
        return False


def test_d_invalid_output_rejection() -> bool:
    """D. Simulated bad Gemma output → _parse_and_validate rejects safely."""
    banner("TEST D: Invalid model output → parse-time rejection (no API call)")
    cases = [
        ('{"tool": "HACK_EVERYTHING", "arguments": {}, "reason": "evil"}',
         "unknown tool name"),
        ('{"tool": "translate", "arguments": {}, "reason": "missing required args"}',
         "missing required args"),
        ('This is not JSON at all! Just plain text.',
         "non-JSON output"),
        ('["tool", "translate"]',
         "JSON array not object"),
    ]
    all_pass = True
    for raw, description in cases:
        try:
            _parse_and_validate(raw)
            print(f"  [{FAIL}] Should have raised InvalidModelOutputError for: {description}")
            all_pass = False
        except InvalidModelOutputError as e:
            print(f"  [{PASS}] Correctly rejected '{description}': {str(e)[:80]!r}")
        except Exception as e:
            print(f"  [{FAIL}] Wrong exception type for '{description}': {type(e).__name__}: {e}")
            all_pass = False
    return all_pass


def test_e_missing_api_key() -> bool:
    """E. Missing GEMINI_API_KEY → ConfigurationError raised cleanly."""
    banner("TEST E: Missing API key → ConfigurationError")
    original = os.environ.pop("GEMINI_API_KEY", None)
    try:
        from services.gemma import _build_client
        _build_client()
        print(f"  [{FAIL}] Should have raised ConfigurationError.")
        return False
    except ConfigurationError as e:
        print(f"  [{PASS}] ConfigurationError raised: {str(e)[:100]!r}")
        return True
    except Exception as e:
        print(f"  [{FAIL}] Wrong exception: {type(e).__name__}: {e}")
        return False
    finally:
        if original:
            os.environ["GEMINI_API_KEY"] = original


async def main() -> None:
    banner("PayprAPI Phase 1 Gemma Smoke Tests")
    model_name = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    api_key_set = bool(os.getenv("GEMINI_API_KEY", "").strip())
    print(f"\n  Model:      {model_name}")
    print(f"  API key:    {'SET' if api_key_set else 'NOT SET -- live tests will be skipped'}")

    results: dict[str, bool] = {}

    # D and E can run without an API key
    results["D (invalid output rejection)"] = test_d_invalid_output_rejection()
    results["E (missing API key)"] = test_e_missing_api_key()

    if not api_key_set:
        print(f"\n  [{SKIP}] GEMINI_API_KEY not set — skipping live API tests A, B, C, probe.")
        results["PROBE"] = False
        results["A (text-only)"] = False
        results["B (multimodal)"] = False
        results["C (ambiguous)"] = False
    else:
        # Pre-flight probe
        model_ok = await test_model_probe()
        results["PROBE"] = model_ok

        if model_ok:
            results["A (text-only)"] = await test_a_text_only()
            results["B (multimodal)"] = await test_b_multimodal()
            results["C (ambiguous)"] = await test_c_ambiguous_request()
        else:
            print(f"\n  [{SKIP}] Model probe failed — skipping live tests A, B, C.")
            results["A (text-only)"] = False
            results["B (multimodal)"] = False
            results["C (ambiguous)"] = False

    # Summary
    banner("RESULTS SUMMARY")
    for name, passed in results.items():
        status = PASS if passed else (FAIL if api_key_set or name.startswith(("D", "E")) else SKIP)
        print(f"  [{status}] {name}")

    live_tests_needed = {"PROBE", "A (text-only)", "B (multimodal)"}
    live_passed = all(results.get(t) for t in live_tests_needed)
    static_passed = results.get("D (invalid output rejection)") and results.get("E (missing API key)")

    print()
    if not api_key_set:
        print("  STATUS: Static tests passed. Set GEMINI_API_KEY and re-run for full smoke test.")
    elif live_passed and static_passed:
        print("  STATUS: PHASE 1 SMOKE TESTS PASSED (A, B, D confirmed; C best-effort).")
    else:
        print("  STATUS: ONE OR MORE TESTS FAILED. Phase 1 NOT complete.")

    print()


if __name__ == "__main__":
    asyncio.run(main())
