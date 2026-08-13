from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.llm_client import ClientSettings, OpenAICompatibleClient, validate_base_url
from backend.ai.schemas import ProviderConfigInput
from backend.config import PROVIDERS
from backend.db.models import ApiConfig
from backend.errors import KeyStoreError, NotFoundError
from backend.security import ApiKeyStore


def effective_base_url(provider: str, base_url: str) -> str:
    value = base_url if provider == "Custom" else PROVIDERS[provider]["base_url"]
    return validate_base_url(value)


def get_record(session: Session) -> ApiConfig | None:
    return session.scalar(select(ApiConfig).order_by(ApiConfig.id).limit(1))


def public_config(session: Session, store: ApiKeyStore) -> dict:
    record = get_record(session)
    if not record:
        return {
            "provider": "",
            "model": "",
            "base_url": "",
            "is_configured": False,
            "key_persisted": False,
            "updated_at": None,
        }
    key_available = bool(store.get(record.provider))
    return {
        "provider": record.provider,
        "model": record.model,
        "base_url": record.base_url,
        "is_configured": bool(record.is_configured and key_available),
        "key_persisted": bool(record.key_persisted and key_available),
        "updated_at": record.updated_at.isoformat(),
    }


def save_config(session: Session, store: ApiKeyStore, payload: ProviderConfigInput) -> dict:
    base_url = effective_base_url(payload.provider, payload.base_url)
    record = get_record(session)
    previous_provider = record.provider if record else None
    persisted = store.set(payload.provider, payload.api_key)
    if previous_provider and previous_provider != payload.provider:
        store.delete(previous_provider)
    if not record:
        record = ApiConfig(
            provider=payload.provider,
            model=payload.model,
            base_url=base_url,
            is_configured=True,
            key_persisted=persisted,
        )
        session.add(record)
    else:
        record.provider = payload.provider
        record.model = payload.model
        record.base_url = base_url
        record.is_configured = True
        record.key_persisted = persisted
    session.commit()
    return public_config(session, store)


def make_client(session: Session, store: ApiKeyStore) -> OpenAICompatibleClient:
    record = get_record(session)
    if not record:
        raise NotFoundError("尚未配置模型 API。")
    api_key = store.require(record.provider)
    return OpenAICompatibleClient(
        ClientSettings(
            provider=record.provider,
            model=record.model,
            base_url=record.base_url,
            api_key=api_key,
        )
    )


def delete_config(session: Session, store: ApiKeyStore) -> None:
    record = get_record(session)
    if not record:
        return
    store.delete(record.provider)
    record.is_configured = False
    record.key_persisted = False
    session.commit()
