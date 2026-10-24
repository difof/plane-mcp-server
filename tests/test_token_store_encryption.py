"""Hosted Plane OAuth refresh tokens must not be written as plaintext."""

import asyncio

import pytest
from cryptography.fernet import Fernet
from key_value.aio.stores.memory import MemoryStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from plane_mcp.storage import _encrypted_redis_store


def test_missing_persistent_oauth_encryption_key_fails_closed(monkeypatch):
    monkeypatch.delenv("PLANE_OAUTH_STORE_ENCRYPTION_KEYS", raising=False)
    with pytest.raises(RuntimeError, match="requires PLANE_OAUTH_STORE_ENCRYPTION_KEYS"):
        _encrypted_redis_store(MemoryStore())


def test_encrypted_store_does_not_expose_token_material(monkeypatch):
    monkeypatch.setenv("PLANE_OAUTH_STORE_ENCRYPTION_KEYS", Fernet.generate_key().decode())
    backend = MemoryStore()
    store = _encrypted_redis_store(backend)
    assert isinstance(store, FernetEncryptionWrapper)

    async def run():
        await store.put(
            "test-key", {"access_token": "sensitive-access-token", "refresh_token": "secret"}, collection="oauth"
        )
        raw = await backend.get("test-key", collection="oauth")
        assert "sensitive-access-token" not in str(raw)
        assert "secret" not in str(raw)
        assert await store.get("test-key", collection="oauth") == {
            "access_token": "sensitive-access-token",
            "refresh_token": "secret",
        }

    asyncio.run(run())


def test_key_rotation_can_decrypt_with_retired_key(monkeypatch):
    first = Fernet.generate_key().decode()
    current = Fernet.generate_key().decode()
    backend = MemoryStore()

    async def run():
        monkeypatch.setenv("PLANE_OAUTH_STORE_ENCRYPTION_KEYS", first)
        await _encrypted_redis_store(backend).put("token", {"access_token": "one"})
        monkeypatch.setenv("PLANE_OAUTH_STORE_ENCRYPTION_KEYS", f"{current},{first}")
        assert (await _encrypted_redis_store(backend).get("token"))["access_token"] == "one"

    asyncio.run(run())
