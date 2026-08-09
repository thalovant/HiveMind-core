"""Reply delivery timing is anchored at the client transport boundary."""

from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest
from hivemind_bus_client import HiveMessage, HiveMessageType
from ovos_bus_client.message import Message

from hivemind_core._metrics import REPLY_DELIVERY
from hivemind_core.performance import (
    message_request_id,
    trace_performance_stage,
)
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


def test_request_id_is_found_in_nested_ovos_metadata():
    message = HiveMessage(
        HiveMessageType.BUS,
        payload=Message(
            "speak",
            {"utterance": "hello"},
            {"metadata": {"qa_query_id": "request-42"}},
        ),
    )

    assert message_request_id(message) == "request-42"


def test_transport_completion_emits_opt_in_correlated_trace(
        monkeypatch):
    delivery = Future()
    client = _client(lambda _payload, _binary: delivery)
    message = HiveMessage(
        HiveMessageType.BUS,
        payload=Message(
            "speak",
            {"utterance": "hello"},
            {"query_id": "request-transport"},
        ),
    )
    monkeypatch.setenv("HIVEMIND_PERFORMANCE_TRACE", "true")
    monkeypatch.setattr(
        "hivemind_core.performance.time.time_ns",
        lambda: 123_000_000,
    )
    logged = []
    monkeypatch.setattr(
        "hivemind_core.performance._LOG.info",
        lambda template, payload: logged.append(template % payload),
    )

    client.send(message)

    assert logged == []
    delivery.set_result(None)
    assert "listener_transport_complete" in logged[0]
    assert '"request_id":"request-transport"' in logged[0]
    assert '"at_unix_ns":123000000' in logged[0]


def test_trace_is_silent_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("HIVEMIND_PERFORMANCE_TRACE", raising=False)
    monkeypatch.setattr(
        "hivemind_core.performance._LOG.info",
        lambda *_args: pytest.fail("disabled trace emitted a log"),
    )

    trace_performance_stage("test", request_id="request-silent")


def test_disabled_transport_trace_does_not_extract_request_id(monkeypatch):
    monkeypatch.delenv("HIVEMIND_PERFORMANCE_TRACE", raising=False)
    monkeypatch.setattr(
        "hivemind_core.protocol.message_request_id",
        lambda _message: pytest.fail("disabled trace extracted request ID"),
    )
    client = _client(lambda _payload, _binary: None)

    client.send(HiveMessage(
        HiveMessageType.BUS,
        payload=Message("speak", {"utterance": "hello"}),
    ))
