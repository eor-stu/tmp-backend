# src/voice/piper_tts_service.py
# Piper TTS service with lazy voice loading
#
# @author n1ghts4kura
# @date 2026-04-25

import os
import wave
from pathlib import Path
from typing import Any

from piper import PiperVoice


class PiperTTSService:
    """Piper TTS service with lazy voice loading."""

    def __init__(self) -> None:
        self._voice: PiperVoice | None = None
        self._model_path = os.environ.get(
            "PIPER_MODEL_PATH",
            "./piper/zh_CN-huayan-medium.onnx",
        )
        self._model_json = os.environ.get(
            "PIPER_MODEL_JSON",
            "./piper/zh_CN-huayan-medium.onnx.json",
        )
        self._output_dir = os.environ.get(
            "PIPER_OUTPUT_DIR",
            "./outputs/tts/",
        )

    def _ensure_output_dir(self, output_path: str) -> None:
        """Create output directory if it doesn't exist."""
        dir_path = Path(output_path).parent
        dir_path.mkdir(parents=True, exist_ok=True)

    def _load_voice(self) -> PiperVoice:
        """Lazy load PiperVoice on first use."""
        if self._voice is None:
            self._voice = PiperVoice.load(
                self._model_path,
                self._model_json,
            )
        return self._voice

    def warm_up(self) -> None:
        """预加载 Piper 模型，避免首次请求的冷启动延迟。"""
        self._load_voice()

    def synthesize(
        self,
        text: str,
        output_path: str | None = None,
        length_scale: float = 1.0,
    ) -> dict[str, Any]:
        """
        Synthesize text to WAV audio file.

        Args:
            text: Text to synthesize
            output_path: Path to write WAV file (auto-generated if None)
            length_scale: Speech rate (higher = slower, default 1.0)

        Returns:
            Dict with success status and audio_path or error
        """
        # Validate text
        if not text or not text.strip():
            return {"success": False, "error": "text is required"}

        # Use fixed output path
        if output_path is None:
            output_path = os.path.join(self._output_dir, "tts.wav")

        # Ensure output directory exists
        self._ensure_output_dir(output_path)

        # Load voice (lazy)
        try:
            voice = self._load_voice()
        except FileNotFoundError:
            return {"success": False, "error": "piper model not found"}
        except Exception as e:
            return {"success": False, "error": f"failed to load voice: {e}"}

        # Synthesize audio chunks
        audio_chunks: list[bytes] = []
        try:
            for chunk in voice.synthesize(text):
                audio_chunks.append(chunk.audio_int16_bytes)
        except Exception as e:
            return {"success": False, "error": f"synthesis failed: {e}"}

        # Combine chunks and write WAV
        audio_data = b"".join(audio_chunks)
        if not audio_data:
            return {"success": False, "error": "no audio generated"}

        try:
            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(22050)  # Piper default
                wav_file.writeframes(audio_data)
        except Exception as e:
            return {"success": False, "error": f"failed to write WAV: {e}"}

        return {"success": True, "audio_path": output_path}


# Singleton instance
piper_tts_service = PiperTTSService()