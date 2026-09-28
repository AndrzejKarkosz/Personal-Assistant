"""ElevenLabs speech-to-text (Scribe) and text-to-speech.

Without ELEVENLABS_API_KEY both return None and the UI falls back to the browser's own
speech recognition / synthesis, so the brain still works end to end.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://api.elevenlabs.io/v1"


@dataclass
class Transcript:
    text: str
    language: str | None = None


class ElevenLabs:
    def __init__(self, settings, cache_dir: Path):
        self.settings = settings
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.settings.elevenlabs_key)

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.settings.elevenlabs_key or ""}

    async def transcribe(self, audio: bytes, filename: str = "speech.webm",
                         language: str | None = None) -> Transcript | None:
        if not self.available:
            return None
        data = {"model_id": self.settings.get("voice.stt_model", "scribe_v2")}
        if language:
            data["language_code"] = language
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{API}/speech-to-text", headers=self._headers(), data=data,
                                     files={"file": (filename, audio, "application/octet-stream")})
        resp.raise_for_status()
        body = resp.json()
        code = (body.get("language_code") or "")[:2].lower() or None
        return Transcript(text=(body.get("text") or "").strip(), language=code)

    async def synthesize(self, text: str) -> str | None:
        """Returns base64 MP3, cached on disk (acknowledgement phrases repeat a lot)."""
        if not self.available or not text.strip():
            return None
        voice = self.settings.voice_id
        model = self.settings.get("voice.tts_model", "eleven_multilingual_v2")
        fmt = self.settings.get("voice.output_format", "mp3_44100_128")
        key = hashlib.sha1(f"{voice}|{model}|{fmt}|{text}".encode()).hexdigest()
        cached = self.cache_dir / f"{key}.mp3"
        if cached.exists():
            return base64.b64encode(cached.read_bytes()).decode()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{API}/text-to-speech/{voice}", params={"output_format": fmt},
                    headers=self._headers(), json={"text": text, "model_id": model},
                )
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        if len(text) < 120:          # cache short, repeatable phrases only
            cached.write_bytes(resp.content)
        return base64.b64encode(resp.content).decode()
