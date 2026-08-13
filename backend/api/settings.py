from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.ai.schemas import ProviderConfigInput
from backend.dependencies import get_key_store, get_session
from backend.security import ApiKeyStore
from backend.services import api_config_service


router = APIRouter(prefix="/api/settings/provider", tags=["settings"])


@router.get("")
def get_provider(
    session: Session = Depends(get_session), store: ApiKeyStore = Depends(get_key_store)
):
    return api_config_service.public_config(session, store)


@router.put("")
def put_provider(
    payload: ProviderConfigInput,
    session: Session = Depends(get_session),
    store: ApiKeyStore = Depends(get_key_store),
):
    result = api_config_service.save_config(session, store, payload)
    return {
        **result,
        "message": (
            "API Key 已保存到操作系统凭据库。"
            if result["key_persisted"]
            else "系统凭据库不可用；Key 仅在本次后端运行期间保留，重启后需重新填写。"
        ),
    }


@router.post("/test")
async def test_provider(
    session: Session = Depends(get_session), store: ApiKeyStore = Depends(get_key_store)
):
    client = api_config_service.make_client(session, store)
    await client.test_connection()
    return {"ok": True, "message": "连接成功。"}


@router.delete("")
def remove_provider(
    session: Session = Depends(get_session), store: ApiKeyStore = Depends(get_key_store)
):
    api_config_service.delete_config(session, store)
    return {"ok": True}

