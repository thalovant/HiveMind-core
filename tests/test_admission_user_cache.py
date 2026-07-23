import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hivemind_core.protocol import HiveMindClientConnection, HiveMindListenerProtocol


def _client(protocol):
    return HiveMindClientConnection(
        key="access-key",
        send_msg=MagicMock(),
        disconnect=MagicMock(),
        hm_protocol=protocol,
        handshake=MagicMock(),
    )


def test_transport_can_seed_resolved_user_without_database_lookup():
    database = MagicMock()
    protocol = SimpleNamespace(identity=SimpleNamespace(private_key="private"))
    client = _client(protocol)
    user = SimpleNamespace(client_id=42, metadata={"noise_pubkey": "pinned"})

    client.cache_resolved_user(user)

    assert client.resolve_user(database) is user
    database.get_client_by_api_key.assert_not_called()
    database.refresh.assert_not_called()


def test_noise_pin_lookup_reuses_transport_resolved_user():
    database = MagicMock()
    database.__enter__.return_value = database
    protocol = object.__new__(HiveMindListenerProtocol)
    protocol.db = database
    client = _client(
        SimpleNamespace(identity=SimpleNamespace(private_key="private")),
    )
    user = SimpleNamespace(client_id=42, metadata={"noise_pubkey": "pinned"})
    client.cache_resolved_user(user)

    assert protocol._get_pinned_client_noise_key(client) == "pinned"
    database.get_client_by_api_key.assert_not_called()
    database.refresh.assert_not_called()


def test_cached_protocol_admission_calls_bounded_initializer():
    protocol = object.__new__(HiveMindListenerProtocol)
    protocol.handle_new_client_protocol = MagicMock(return_value=True)
    client = _client(
        SimpleNamespace(identity=SimpleNamespace(private_key="private")),
    )
    client.cache_resolved_user(SimpleNamespace(client_id=42))

    assert protocol.handle_new_client_protocol_cached(client) is True
    protocol.handle_new_client_protocol.assert_called_once_with(client)


@pytest.mark.parametrize("age", [None, 5.1])
def test_cached_protocol_admission_rejects_missing_or_stale_cache(age):
    protocol = object.__new__(HiveMindListenerProtocol)
    protocol.handle_new_client_protocol = MagicMock(return_value=True)
    client = _client(
        SimpleNamespace(identity=SimpleNamespace(private_key="private")),
    )
    if age is not None:
        client.cache_resolved_user(SimpleNamespace(client_id=42))
        client._resolved_user_ts = time.time() - age

    with pytest.raises(
            RuntimeError,
            match="requires a current resolved user",
    ):
        protocol.handle_new_client_protocol_cached(client)

    protocol.handle_new_client_protocol.assert_not_called()
