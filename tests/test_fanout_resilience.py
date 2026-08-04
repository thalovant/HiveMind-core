"""Regression coverage for the downstream fan-out hot path."""

from unittest.mock import MagicMock, patch

from hivemind_bus_client.message import HiveMessage, HiveMessageType

from hivemind_core.protocol import HiveMindListenerProtocol


def _connection(peer):
    connection = MagicMock()
    connection.peer = peer
    return connection


def _protocol(*connections):
    protocol = object.__new__(HiveMindListenerProtocol)
    protocol.clients = {connection.peer: connection
                        for connection in connections}
    return protocol


def test_one_raising_peer_does_not_block_other_clients():
    first = _connection("first")
    broken = _connection("broken")
    last = _connection("last")
    broken.send.side_effect = ValueError("broken peer crypto state")
    protocol = _protocol(first, broken, last)
    message = HiveMessage(HiveMessageType.BUS, payload={"type": "speak"})

    protocol._fanout(message)

    first.send.assert_called_once()
    broken.send.assert_called_once()
    last.send.assert_called_once()


def test_fanout_serializes_once_and_reuses_plaintext():
    clients = [_connection(f"peer-{index}") for index in range(5)]
    protocol = _protocol(*clients)
    message = HiveMessage(HiveMessageType.BUS, payload={"type": "speak"})
    original_serialize = HiveMessage.serialize
    calls = 0

    def counting_serialize(self):
        nonlocal calls
        calls += 1
        return original_serialize(self)

    with patch.object(HiveMessage, "serialize", counting_serialize):
        protocol._fanout(message)

    assert calls == 1
    for client in clients:
        args, _ = client.send.call_args
        assert args[0] is message
        assert isinstance(args[1], str)


def test_binary_fanout_defers_wire_encoding_to_each_connection():
    clients = [_connection(f"peer-{index}") for index in range(3)]
    protocol = _protocol(*clients)
    message = HiveMessage(HiveMessageType.BINARY, payload=b"binary payload")

    protocol._fanout(message)

    for client in clients:
        client.send.assert_called_once_with(message, None)


def test_fanout_uses_a_stable_client_snapshot():
    first = _connection("first")
    last = _connection("last")
    protocol = _protocol(first, last)
    message = HiveMessage(HiveMessageType.BUS, payload={"type": "speak"})

    first.send.side_effect = lambda *_: protocol.clients.pop(last.peer)
    protocol._fanout(message)

    first.send.assert_called_once()
    last.send.assert_called_once()
