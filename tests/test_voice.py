"""ElevenLabs speech in and out (HTTP mocked), language detection and persona defaults."""
import base64
import functools

import httpx

from brain.voice import persona
from brain.voice.elevenlabs import ElevenLabs


async def test_voice_is_off_without_a_key(settings, tmp_path):
    voice = ElevenLabs(settings, tmp_path)
    assert await voice.transcribe(b"audio") is None and await voice.synthesize("hej") is None


async def test_speech_is_cached_and_transcripts_parsed(settings, tmp_path, monkeypatch, http):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi")
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/speech-to-text"):
            return httpx.Response(200, json={"text": " co słychać ", "language_code": "pl"})
        if b"zepsute" in request.content:
            return httpx.Response(500)
        return httpx.Response(200, content=b"mp3")

    http(handler)
    voice = ElevenLabs(settings, tmp_path)
    mp3 = base64.b64encode(b"mp3").decode()
    assert await voice.synthesize("Jasne, szefie.") == mp3
    assert await voice.synthesize("Jasne, szefie.") == mp3 and len(calls) == 1      # short phrases come from disk
    assert calls[0].headers["xi-api-key"] == "xi" and calls[0].url.params["output_format"] == "mp3_44100_128"
    assert await voice.synthesize("zepsute") is None                                  # TTS down -> browser voice

    transcript = await voice.transcribe(b"audio", language="pl")
    assert (transcript.text, transcript.language) == ("co słychać", "pl")


def test_language_detection_and_persona_defaults(settings, tmp_path, monkeypatch):
    assert persona.detect_language("przypomnij mi jutro") == "pl"
    assert persona.detect_language("remind me tomorrow") == "en"
    assert persona.detect_language("42", default="en") == "en"

    path = tmp_path / "persona.md"
    persona.save({}, "", path)                                         # a persona file with nothing in it
    monkeypatch.setattr(persona, "load", functools.partial(persona.load, path))
    assert persona.system_prompt(settings) == "You are Alfred, the personal assistant of Andrzej."
    assert persona.ack_phrase(settings, "en") == "Of course, boss. I'm on it."
    assert persona.confirm_prompt(settings, "pl", "wyślę maila") == "Zanim to zrobię: wyślę maila. Potwierdzasz?"
