"""
PayprAPI Pay-Per-Use AI API Marketplace
FastAPI AI Services Backend
"""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from routers import translate, summarize, sentiment, image_gen, agent
from services.algorand import AlgorandService

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("marketplace.ai-services")

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PayprAPI AI Services",
    description="Pay-per-use AI API Marketplace — AI Services Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"INCOMING REQUEST: {request.method} {request.url.path}")
    return await call_next(request)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(translate.router, prefix="/api/translate", tags=["Translation"])
app.include_router(summarize.router, prefix="/api/summarize", tags=["Summarization"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment Analysis"])
app.include_router(image_gen.router, prefix="/api/image", tags=["Image Generation"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent / Gemma"])


@app.get("/")
async def root():
    return {
        "service": "PayprAPI AI Services",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            {"path": "/api/translate", "description": "Text translation", "price": "0.001 ALGO"},
            {"path": "/api/summarize", "description": "Text summarization", "price": "0.002 ALGO"},
            {"path": "/api/sentiment", "description": "Sentiment analysis", "price": "0.001 ALGO"},
            {"path": "/api/image", "description": "Image generation", "price": "0.005 ALGO"},
            {"path": "/api/agent/select-tool", "description": "Gemma 4 tool selection (no payment required)", "price": "free"},
        ],
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-services"}


@app.get("/services")
async def list_services():
    """Return all available AI services with pricing"""
    return {
        "services": [
            {
                "id": "translate",
                "name": "Language Translation",
                "description": "Translate text between 50+ languages using neural machine translation",
                "endpoint": "/api/translate",
                "price": 0.001,
                "currency": "ALGO",
                "category": "Language",
                "icon": "🌐",
                "example_request": {"text": "Hello world", "source_lang": "en", "target_lang": "es"},
            },
            {
                "id": "summarize",
                "name": "Text Summarization",
                "description": "Generate concise summaries of long documents and articles",
                "endpoint": "/api/summarize",
                "price": 0.002,
                "currency": "ALGO",
                "category": "NLP",
                "icon": "📝",
                "example_request": {"text": "Long article text...", "max_sentences": 3},
            },
            {
                "id": "sentiment",
                "name": "Sentiment Analysis",
                "description": "Analyze emotional tone and sentiment of text with confidence scores",
                "endpoint": "/api/sentiment",
                "price": 0.001,
                "currency": "ALGO",
                "category": "Analytics",
                "icon": "🎯",
                "example_request": {"text": "This product is amazing!"},
            },
            {
                "id": "image_gen",
                "name": "Image Generation",
                "description": "Generate AI images from text prompts using diffusion models",
                "endpoint": "/api/image/generate",
                "price": 0.005,
                "currency": "ALGO",
                "category": "Creative",
                "icon": "🎨",
                "example_request": {"prompt": "A futuristic city at sunset", "style": "realistic"},
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("AI_SERVICE_HOST", "0.0.0.0"),
        port=int(os.getenv("AI_SERVICE_PORT", 8001)),
        reload=True,
    )
