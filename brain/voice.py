"""Ears and mouth: ElevenLabs speech-to-text (Scribe) and text-to-speech.

Without ELEVENLABS_API_KEY both return None and the UI uses the browser's own (free) recognition and voice.
Short phrases ("Witaj z powrotem, szefie.") are cached on disk, so they cost nothing the second time.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

log = logging.getLogger("alfred.voice")

API = "https://api.elevenlabs.io/v1"


@dataclass
class Transcript:
    text: str
    language: str | None = None   # "pl", "en", ...


class ElevenLabs:
    def __init__(self, settings, cache_dir: Path, on_usage: Callable[..., None] = lambda **used: None,
                 on_error: Callable[[str], None] = lambda message: None):
        self.settings = settings
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.on_usage = on_usage   # tts_chars / stt_s of each billed call - the brain prices them
        self.on_error = on_error   # why there is no ElevenLabs voice (the UI falls back to the browser's)

    async def transcribe(self, audio: bytes, filename: str = "speech.webm",
                         language: str | None = None) -> Transcript | None:
        key = self.settings.elevenlabs_key
        if not key:
            return None
        form = {"model_id": self.settings.get("voice.stt_model", "scribe_v2")} | (
            {"language_code": language} if language else {})
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{API}/speech-to-text", headers={"xi-api-key": key}, data=form,
                                     files={"file": (filename, audio, "application/octet-stream")})
        resp.raise_for_status()
        body = resp.json()
        # billed per second of audio; the last word's end time is the length of what was said
        self.on_usage(stt_s=max((float(w.get("end") or 0) for w in body.get("words") or []), default=0.0))
        return Transcript((body.get("text") or "").strip(), (body.get("language_code") or "")[:2].lower() or None)

    async def synthesize(self, text: str) -> str | None:
        """Speech for `text` as base64 mp3, or None (no key, voice switched off, or ElevenLabs failed)."""
        key = self.settings.elevenlabs_key
        if not key or not text.strip() or not self.settings.get("voice.tts_enabled", True):
            return None
        voice, s = self.settings.voice_id, self.settings
        model, fmt = s.get("voice.tts_model", "eleven_multilingual_v2"), s.get("voice.output_format", "mp3_44100_128")
        tuning = s.get("voice.settings") or {}
        cached = self.cache_dir / (hashlib.sha1(f"{voice}|{model}|{fmt}|{sorted(tuning.items())}|{text}".encode())
                                   .hexdigest() + ".mp3")
        if cached.exists():
            return base64.b64encode(cached.read_bytes()).decode()
        body = {"text": text, "model_id": model} | ({"voice_settings": tuning} if tuning else {})
        for attempt in (1, 2):              # once more after a dropped connection, a busy or a failing ElevenLabs
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(f"{API}/text-to-speech/{voice}", params={"output_format": fmt},
                                             headers={"xi-api-key": key}, json=body)
                error = f"HTTP {resp.status_code}: {resp.text[:300]}" if resp.is_error else None
                if not error or (resp.status_code < 500 and resp.status_code != 429):
                    break
            except httpx.HTTPError as exc:
                error = f"{type(exc).__name__}: {exc}"
        if error:
            log.warning("ElevenLabs TTS failed: %s", error)
            self.on_error(error)
            return None
        self.on_usage(tts_chars=len(text))  # cached phrases above cost nothing
        if len(text) < 120:
            cached.write_bytes(resp.content)
        return base64.b64encode(resp.content).decode()
