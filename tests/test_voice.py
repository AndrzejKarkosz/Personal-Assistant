import base64
import functools
import json

import httpx

from brain import persona
from brain.voice import ElevenLabs, spoken


async def test_voice_is_off_without_a_key(settings, tmp_path):
    voice = ElevenLabs(settings, tmp_path)
    assert await voice.transcribe(b"audio") is None and await voice.synthesize("hej") is None


async def test_speech_is_cached_and_transcripts_parsed(settings, tmp_path, monkeypatch, http):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi")
    settings.data["voice"]["tts_enabled"] = True             # off by default: the browser speaks for free
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
    assert await voice.synthesize("Jasne, szefie.") == mp3 and len(calls) == 1
    assert calls[0].headers["xi-api-key"] == "xi" and calls[0].url.params["output_format"] == "mp3_44100_128"
    errors = []
    voice.on_error = errors.append
    before = len(calls)
    assert await voice.synthesize("zepsute") is None
    assert len(calls) == before + 2 and errors == ["HTTP 500: "]          # tried twice, then says why

    transcript = await voice.transcribe(b"audio", language="pl")
    assert (transcript.text, transcript.language) == ("co słychać", "pl")

    settings.data["voice"]["tts_enabled"] = False            # answers off, listening still on
    before = len(calls)
    assert await voice.synthesize("Nowe zdanie.") is None and len(calls) == before
    assert (await voice.transcribe(b"audio")).text == "co słychać"


def test_language_detection_and_persona_defaults(settings, tmp_path, monkeypatch):
    assert persona.detect_language("przypomnij mi jutro") == "pl"
    assert persona.detect_language("remind me tomorrow") == "en"
    assert persona.detect_language("42", default="en") == "en"

    path = tmp_path / "persona.md"
    persona.save({}, "", path)
    monkeypatch.setattr(persona, "load", functools.partial(persona.load, path))
    assert persona.system_prompt(settings) == "You are Alfred, the personal assistant of Ola."
    assert persona.confirm_prompt("pl", "wyślę maila") == "Zanim to zrobię: wyślę maila. Potwierdzasz?"


async def test_only_the_start_is_spoken_and_quota_stops_calls(settings, tmp_path, monkeypatch, http):
    long = "Zrobione, szefie. " + "Bardzo długie wyjaśnienie, którego nikt nie słucha. " * 10
    assert spoken(long, 200) == "Zrobione, szefie. Bardzo długie wyjaśnienie, którego nikt nie słucha. " \
                                "Bardzo długie wyjaśnienie, którego nikt nie słucha. Bardzo długie wyjaśnienie, " \
                                "którego nikt nie słucha."
    assert spoken("słowo " * 100, 20) == "słowo słowo słowo…"   # one endless sentence: cut at a word
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi")
    settings.data["voice"]["tts_enabled"] = True             # off by default: the browser speaks for free
    sent = []

    def handler(request):
        sent.append(request.content)
        return httpx.Response(401, json={"detail": {"code": "quota_exceeded"}}) if len(sent) > 2 else \
            httpx.Response(200, content=b"mp3")

    http(handler)
    voice = ElevenLabs(settings, tmp_path)
    await voice.synthesize(long)
    assert len(json.loads(sent[0])["text"]) <= 200
    question = "Zanim to zrobię: " + "x " * 120 + ". Potwierdzasz?"
    await voice.synthesize(question, whole=True)                     # a yes/no question is spoken whole
    assert json.loads(sent[1])["text"] == question
    assert await voice.synthesize("Pierwsze.") is None and await voice.synthesize("Drugie.") is None
    assert len(sent) == 3                                             # out of quota: no more calls for an hour
