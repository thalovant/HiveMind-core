"""Reply delivery timing is anchored at the client transport boundary."""

from concurrent.futures import Future
from unittest.mock import MagicMock

from hivemind_bus_client import HiveMessage, HiveMessageType
from ovos_bus_client.message import Message

from hivemind_core._metrics import REPLY_DELIVERY
from hivemind_core.protocol import HiveMindClientConnection


def _client(send_msg):
    return HiveMindClientConnection(
        key="test-key",
        send_msg=send_msg,
        disconnect=MagicMock(),
        hm_protocol=MagicMock(),
        handshake=MagicMock(),
    )


def test_public_reply_is_observed_only_after_transport_future_completes(
        monkeypatch):
    delivery = Future()
    client = _client(lambda _payload, _binary: delivery)
    message = HiveMessage(
        HiveMessageType.BUS,
        payload=Message("speak", {"utterance": "hello"}),
    )
    clock = iter((10.0, 10.125))
    monkeypatch.setattr(
        "hivemind_core.protocol.time.monotonic",
        lambda: next(clock),
    )
    initial = REPLY_DELIVERY.snapshot()

    returned = client.send(message)

    assert returned is delivery
    assert REPLY_DELIVERY.snapshot()["count"] == initial["count"]
    delivery.set_result(None)
    observed = REPLY_DELIVERY.snapshot()
    assert observed["count"] == initial["count"] + 1
    assert observed["sum_ms"] == initial["sum_ms"] + 125
    assert observed["buckets"]["le_100"] == initial["buckets"]["le_100"]
    assert observed["buckets"]["le_250"] == initial["buckets"]["le_250"] + 1


def test_handshake_traffic_is_not_counted_as_reply_delivery():
    client = _client(lambda _payload, _binary: None)
    initial = REPLY_DELIVERY.snapshot()["count"]

    client.send(HiveMessage(HiveMessageType.HELLO, payload={}))

    assert REPLY_DELIVERY.snapshot()["count"] == initial
