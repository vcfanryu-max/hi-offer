from __future__ import annotations

import threading

import keyring

from backend.config import API_KEY_SERVICE
from backend.errors import KeyStoreError


class ApiKeyStore:
    """Store secrets in the OS vault; memory is an explicit non-persistent fallback."""

    _memory: dict[str, str] = {}
    _lock = threading.Lock()

    @staticmethod
    def _account(provider: str) -> str:
        return f"provider:{provider.casefold()}"

    def set(self, provider: str, api_key: str) -> bool:
        account = self._account(provider)
        try:
            keyring.set_password(API_KEY_SERVICE, account, api_key)
            with self._lock:
                self._memory.pop(account, None)
            return True
        except Exception:
            # Some Windows keyring backends surface CredWrite failures as
            # pywintypes.error/OSError instead of KeyringError. The contract is
            # still the same: never write the secret to disk; fall back to the
            # current backend process only.
            with self._lock:
                self._memory[account] = api_key
            return False

    def get(self, provider: str) -> str | None:
        account = self._account(provider)
        try:
            value = keyring.get_password(API_KEY_SERVICE, account)
            if value:
                return value
        except Exception:
            pass
        with self._lock:
            return self._memory.get(account)

    def delete(self, provider: str) -> None:
        account = self._account(provider)
        try:
            keyring.delete_password(API_KEY_SERVICE, account)
        except Exception:
            pass
        with self._lock:
            self._memory.pop(account, None)

    def require(self, provider: str) -> str:
        value = self.get(provider)
        if not value:
            raise KeyStoreError("API Key 不可用。请重新保存后再生成。")
        return value
