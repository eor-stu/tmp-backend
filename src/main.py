# src/main.py
# FastAPI application entry point with whisper-server lifecycle integration
#
# @author n1ghts4kura
# @date 2026-04-24

import argparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import dspy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.logger import info, error
from src.voice.whisper_manager import whisper_manager
from src.voice.stt import router as stt_router
from src.voice.tts import router as tts_router
from src.triager.routing import triager_router
from src.car.routes import router as car_router
from src.map.routes import router as map_router
from src.vision.routes import router as vision_router
from src.face.routes import router as face_router


def parse_args():
    parser = argparse.ArgumentParser(description="UFC 2026 Backend Server")
    parser.add_argument(
        "--llm_online",
        action="store_true",
        help="Enable online LLM (DeepSeek). Default: False (uses local Llama)"
    )
    return parser.parse_args()


args = parse_args()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: start/stop whisper-server and configure LLM."""
    # Startup
    whisper_manager.start()
    if args.llm_online:
        from src.llm.deepseek import DeepseekLM
        dspy.configure(lm=DeepseekLM())
        info("Using online LLM: DeepSeek")
    else:
        from src.llm.llama import LlamaCppLM
        dspy.configure(lm=LlamaCppLM(
            model_id="main-lm",
            model_filename="LFM2.5-1.2B-Instruct-Q4_K_M"
        ))
        info("Using local LLM: LFM")
    yield
    # Shutdown
    whisper_manager.stop()


app = FastAPI(
    title="UFC 2026 Backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stt_router, prefix="/stt", tags=["stt"])
app.include_router(tts_router, prefix="/tts", tags=["tts"])
app.include_router(triager_router, tags=["triager"])
app.include_router(car_router)
app.include_router(map_router)
app.include_router(vision_router)
app.include_router(face_router)


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    whisper_ok = whisper_manager.is_ready()
    return {
        "status": "ok",
        "whisper_available": whisper_ok,
    }


@app.get("/")
def root() -> dict:
    """Root endpoint."""
    return {"message": "UFC 2026 Backend"}


@app.get("/get_newest_audio")
def get_newest_audio() -> FileResponse:
    """Return the newest TTS audio file."""
    from src.utils import ROOT_DIR
    return FileResponse(
        path=ROOT_DIR / "outputs/tts/tts.wav",
        media_type="audio/wav",
        filename="tts.wav"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
