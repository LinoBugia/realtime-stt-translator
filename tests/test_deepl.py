"""Tests for the DeepL translation layer (/api/translate, formality, context)."""

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(main, "APP_PASSWORD", "test-password")
    monkeypatch.setattr(main, "AUTH_SECRET", "test-secret")
    monkeypatch.setattr(main, "AUTH_ENABLED", True)
    monkeypatch.setattr(main, "ENABLED_ENGINES", {"webspeech", "elevenlabs"})
    return TestClient(main.app)


def _login(client):
    client.post(
        "/login", data={"password": "test-password", "next": "/"}, follow_redirects=False
    )


def test_normalize_formality():
    assert main._normalize_formality("more") == "more"
    assert main._normalize_formality("formal") == "more"
    assert main._normalize_formality("prefer_more") == "more"
    assert main._normalize_formality("less") == "less"
    assert main._normalize_formality("informal") == "less"
    assert main._normalize_formality("default") is None
    assert main._normalize_formality("") is None
    assert main._normalize_formality(None) is None
    assert main._normalize_formality(42) is None


def test_deepl_lang_mapping():
    assert main._deepl_source_lang("en-US") == "EN"
    assert main._deepl_source_lang("de") == "DE"
    assert main._deepl_target_lang("en") == "EN-US"
    assert main._deepl_target_lang("pt") == "PT-PT"
    assert main._deepl_target_lang("de") == "DE"
    assert main._deepl_target_lang("en-GB") == "EN-GB"


def test_api_translate_requires_auth(client):
    resp = client.post("/api/translate", json={"text": "hola", "target_lang": "de"})
    assert resp.status_code == 401


def test_api_translate_validates_input(client):
    _login(client)
    resp = client.post("/api/translate", json={"target_lang": "de"})
    assert resp.status_code == 400
    resp = client.post("/api/translate", json={"text": "hola"})
    assert resp.status_code == 400
    resp = client.post(
        "/api/translate", json={"text": "x" * (main.MAX_TEXT_LENGTH + 1), "target_lang": "de"}
    )
    assert resp.status_code == 400


def test_api_translate_uses_deepl(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPL_API_KEY", "test-key:fx")
    calls = []

    async def fake_deepl(text, *, src, dest, formality=None, context=None):
        calls.append({"text": text, "src": src, "dest": dest, "formality": formality, "context": context})
        return f"{dest}:{text}"

    monkeypatch.setattr(main, "_deepl_translate", fake_deepl)

    _login(client)
    resp = client.post(
        "/api/translate",
        json={
            "text": "hola mundo",
            "source_lang": "es",
            "target_lang": "de",
            "formality": "more",
            "context": "frase anterior",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"translation": "de:hola mundo", "provider": "deepl"}
    assert calls == [
        {
            "text": "hola mundo",
            "src": "es",
            "dest": "de",
            "formality": "more",
            "context": "frase anterior",
        }
    ]


def test_api_translate_googletrans_fallback(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPL_API_KEY", "")

    class FakeTranslation:
        def __init__(self, text):
            self.text = text

    class FakeAsyncTranslator:
        async def translate(self, text, src, dest):
            return FakeTranslation(f"{dest}:{text}")

    monkeypatch.setattr(main, "Translator", FakeAsyncTranslator)

    _login(client)
    resp = client.post(
        "/api/translate", json={"text": "hola", "source_lang": "es", "target_lang": "en"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"translation": "en:hola", "provider": "googletrans"}


def test_translate_languages_curated_for_deepl(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPL_API_KEY", "test-key:fx")
    _login(client)
    resp = client.get("/api/translate/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "deepl"
    codes = {lang["code"] for lang in data["languages"]}
    # v1 languages of the live speech translator brief.
    assert {"en", "es", "de", "pl", "fr"} <= codes


def test_ws_final_uses_deepl_formality_and_context(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPL_API_KEY", "test-key:fx")
    calls = []

    async def fake_deepl(text, *, src, dest, formality=None, context=None):
        calls.append({"text": text, "src": src, "dest": dest, "formality": formality, "context": context})
        return f"{dest}:{text}"

    monkeypatch.setattr(main, "_deepl_translate", fake_deepl)

    _login(client)
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        ws.send_json(
            {"type": "config", "translate": {"src": "es", "dests": ["de"], "formality": "more"}}
        )
        ws.send_json({"type": "final", "text": "Hola"})
        first = ws.receive_json()
        ws.send_json({"type": "final", "text": "Buenos dias"})
        second = ws.receive_json()

    assert first["translations"] == {"de": "de:Hola"}
    assert second["translations"] == {"de": "de:Buenos dias"}
    # First final has no context; the second gets the previous committed sentence.
    assert calls[0] == {
        "text": "Hola",
        "src": "es",
        "dest": "de",
        "formality": "more",
        "context": None,
    }
    assert calls[1] == {
        "text": "Buenos dias",
        "src": "es",
        "dest": "de",
        "formality": "more",
        "context": "Hola",
    }


def test_ws_message_formality_overrides_session(client, monkeypatch):
    monkeypatch.setattr(main, "DEEPL_API_KEY", "test-key:fx")
    calls = []

    async def fake_deepl(text, *, src, dest, formality=None, context=None):
        calls.append(formality)
        return f"{dest}:{text}"

    monkeypatch.setattr(main, "_deepl_translate", fake_deepl)

    _login(client)
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        ws.send_json(
            {"type": "config", "translate": {"src": "es", "dests": ["de"], "formality": "more"}}
        )
        ws.send_json({"type": "final", "text": "Hola", "formality": "less"})
        ws.receive_json()

    assert calls == ["less"]
