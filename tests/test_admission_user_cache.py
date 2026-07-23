from types import SimpleNamespace
from unittest.mock import MagicMock

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
