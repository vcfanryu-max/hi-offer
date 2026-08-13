from __future__ import annotations

from pathlib import Path
import importlib

import keyring
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.ai.schemas import ProviderConfigInput
from backend.db.session import Base
from backend.security import ApiKeyStore
from backend.services import api_config_service


ROOT = Path(__file__).resolve().parents[1]


def test_local_first_frontend_contract_is_present():
    required_pages = [
        ROOT / "frontend" / "app" / "page.tsx",
        ROOT / "frontend" / "app" / "workspace" / "page.tsx",
        ROOT / "frontend" / "app" / "profile" / "page.tsx",
        ROOT / "frontend" / "app" / "dev" / "prompts" / "page.tsx",
    ]
    assert all(path.is_file() for path in required_pages)

    action_bar = (ROOT / "frontend" / "components" / "TextActionBar.tsx").read_text(encoding="utf-8")
    assert "navigator.clipboard.writeText" in action_bar
    assert "new Blob" in action_bar
    assert "anchor.download" in action_bar

    frontend_source = "\n".join(path.read_text(encoding="utf-8") for path in required_pages)
    assert "登录" not in frontend_source
    assert "注册" not in frontend_source


def test_streamlit_and_duplicate_prompt_sources_are_removed():
    assert not (ROOT / "streamlit_app.py").exists()
    assert not any(path.is_file() for path in (ROOT / "app_v2").rglob("*"))
    assert not any(path.is_file() for path in (ROOT / "prompt_library").rglob("*"))


def test_api_key_store_uses_explicit_memory_fallback_for_windows_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError(1312, "no Windows logon session")

    monkeypatch.setattr(keyring, "set_password", fail)
    monkeypatch.setattr(keyring, "get_password", fail)
    monkeypatch.setattr(keyring, "delete_password", fail)
    store = ApiKeyStore()
    provider = "ContractTestProvider"
    assert store.set(provider, "fictional-test-key") is False
    assert store.get(provider) == "fictional-test-key"
    store.delete(provider)
    assert store.get(provider) is None


def test_switching_provider_removes_previous_key(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'settings.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    class FakeStore:
        def __init__(self):
            self.keys: dict[str, str] = {}

        def set(self, provider: str, value: str) -> bool:
            self.keys[provider] = value
            return True

        def get(self, provider: str) -> str | None:
            return self.keys.get(provider)

        def delete(self, provider: str) -> None:
            self.keys.pop(provider, None)

    store = FakeStore()
    monkeypatch.setattr(api_config_service, "effective_base_url", lambda _provider, base_url: base_url or "https://example.com")
    with Session() as session:
        first = ProviderConfigInput(provider="DeepSeek", model="deepseek-chat", api_key="fictional-one")
        second = ProviderConfigInput(provider="OpenAI", model="gpt-5-mini", api_key="fictional-two")
        api_config_service.save_config(session, store, first)
        api_config_service.save_config(session, store, second)
        assert "DeepSeek" not in store.keys
        assert store.keys == {"OpenAI": "fictional-two"}
        public = api_config_service.public_config(session, store)
        assert public["provider"] == "OpenAI"
        assert "api_key" not in public


def test_prompt_lab_router_is_only_mounted_in_debug_mode(monkeypatch):
    import backend.config as config
    import backend.main as main_module

    monkeypatch.setattr(config, "DEBUG_MODE", False)
    production = importlib.reload(main_module).app
    assert TestClient(production).get("/api/dev/prompts").status_code == 404

    monkeypatch.setattr(config, "DEBUG_MODE", True)
    development = importlib.reload(main_module).app
    assert TestClient(development).get("/api/dev/prompts").status_code == 200

    monkeypatch.setattr(config, "DEBUG_MODE", False)
    importlib.reload(main_module)
