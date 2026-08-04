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


def test_public_reply_is_observed_only_after_transport_future_completes():
    delivery = Future()
    client = _client(lambda _payload, _binary: delivery)
    message = HiveMessage(
        HiveMessageType.BUS,
        payload=Message("speak", {"utterance": "hello"}),
    )
    initial = REPLY_DELIVERY.snapshot()["count"]

    returned = client.send(message)

    assert returned is delivery
    assert REPLY_DELIVERY.snapshot()["count"] == initial
    delivery.set_result(None)
    assert REPLY_DELIVERY.snapshot()["count"] == initial + 1


def test_handshake_traffic_is_not_counted_as_reply_delivery():
    client = _client(lambda _payload, _binary: None)
    initial = REPLY_DELIVERY.snapshot()["count"]

    client.send(HiveMessage(HiveMessageType.HELLO, payload={}))

    assert REPLY_DELIVERY.snapshot()["count"] == initial
