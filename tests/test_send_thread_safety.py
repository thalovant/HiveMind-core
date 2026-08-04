"""Regression coverage for concurrent writes to a Noise connection."""

import threading
import time
from unittest.mock import MagicMock

from hivemind_bus_client import HiveMessage, HiveMessageType

from hivemind_core.protocol import HiveMindClientConnection


class _FakeNoiseTransport:
    """Assign a nonce atomically, then yield before returning the frame."""

    def __init__(self):
        self._send_lock = threading.Lock()
        self._nonce = 0

    def encrypt_frame(self, payload):
        with self._send_lock:
            nonce = self._nonce
            self._nonce += 1
        time.sleep(0)
        return nonce


def test_v3_frames_reach_transport_in_nonce_order():
    sent = []
    sent_lock = threading.Lock()

    def send_msg(payload, is_binary):
        with sent_lock:
            sent.append(payload)

    client = HiveMindClientConnection(
        key="test-key",
        send_msg=send_msg,
        disconnect=MagicMock(),
        hm_protocol=MagicMock(),
        handshake=MagicMock(),
    )
    client.noise_transport = _FakeNoiseTransport()
    message = HiveMessage(HiveMessageType.BUS, payload={"type": "speak"})
    frames_per_thread = 200
    start = threading.Barrier(3)

    def sender():
        start.wait()
        for _ in range(frames_per_thread):
            client.send(message)

    threads = [threading.Thread(target=sender) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(sent) == 3 * frames_per_thread
    assert sent == list(range(len(sent)))
