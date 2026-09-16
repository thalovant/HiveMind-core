import queue
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hivemind_core.config import _DEFAULT
from hivemind_core.protocol import HiveMindListenerProtocol


class FakeClientDatabase:
    def __init__(self, user):
        self.user = user
        self.lookups = 0
        self.updates = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get_client_by_api_key(self, key):
        self.lookups += 1
        if key == "access-key":
            return self.user
        return None

    def update_item(self, user):
        self.updates += 1
        self.user = user

    def update_last_seen(self, key, seen_at):
        self.lookups += 1
        if key != "access-key":
            return False
        self.user.last_seen = max(self.user.last_seen, seen_at)
        self.updates += 1
        return True


def _protocol(db):
    agent = MagicMock()
    agent.bus = MagicMock()
    agent.callbacks = MagicMock()
    agent.get_bus.return_value = agent.bus
    proto = HiveMindListenerProtocol(
        agent_protocol=agent,
        db=db,
        require_crypto=False,
        handshake_enabled=True,
        policy_chain=MagicMock(),
    )
    return proto


def _client(peer="peer", key="access-key"):
    return SimpleNamespace(
        disconnect=MagicMock(),
        key=key,
        last_seen=-1,
        peer=peer,
        sess=SimpleNamespace(serialize=MagicMock(return_value={})),
    )


def test_performance_defaults_are_bounded():
    assert _DEFAULT["last_seen_update_interval"] == 60
    assert _DEFAULT["reply_delivery_timeout"] == 5


def test_last_seen_touches_are_queued_and_coalesced_per_client_key():
    user = SimpleNamespace(last_seen=0)
    db = FakeClientDatabase(user)
    proto = _protocol(db)
    proto.last_seen_update_interval = 30
    queued = []
    proto._last_seen_queue = MagicMock()
    proto._last_seen_queue.put_nowait.side_effect = queued.append
    client = _client()

    with (
        patch("hivemind_core.protocol.time.time", side_effect=[1000.0, 1005.0, 1031.0]),
        patch("hivemind_core.protocol.time.monotonic", side_effect=[100.0, 105.0, 131.0]),
    ):
        proto.touch_last_seen(client)
        proto.touch_last_seen(client)
        proto.touch_last_seen(client)

    assert queued == [(client, 1000.0), (client, 1031.0)]
    assert client.last_seen == 1031.0
    assert db.lookups == 0
    assert db.updates == 0


def test_zero_last_seen_interval_queues_every_message_without_database_io():
    user = SimpleNamespace(last_seen=0)
    db = FakeClientDatabase(user)
    proto = _protocol(db)
    proto.last_seen_update_interval = 0
    queued = []
    proto._last_seen_queue = MagicMock()
    proto._last_seen_queue.put_nowait.side_effect = queued.append
    client = _client()

    with (
        patch("hivemind_core.protocol.time.time", side_effect=[100.0, 101.0]),
        patch("hivemind_core.protocol.time.monotonic", side_effect=[10.0, 11.0]),
    ):
        proto.touch_last_seen(client)
        proto.touch_last_seen(client)

    assert queued == [(client, 100.0), (client, 101.0)]
    assert client.last_seen == 101.0
    assert db.lookups == 0
    assert db.updates == 0


def test_full_queue_defers_retry_and_rate_limits_warnings():
    proto = _protocol(FakeClientDatabase(SimpleNamespace(last_seen=0)))
    proto.last_seen_update_interval = 30
    proto._last_seen_queue = MagicMock()
    proto._last_seen_queue.put_nowait.side_effect = queue.Full
    # Two different keys, because one client touched twice returns at the
    # debounce gate the second time and never reaches the full queue -- so the
    # test passed whether or not the warning was throttled at all.
    first = _client(peer="one", key="access-key-one")
    second = _client(peer="two", key="access-key-two")

    with (
        patch("hivemind_core.protocol.time.time", return_value=100.0),
        patch("hivemind_core.protocol.time.monotonic", return_value=10.0),
        patch("hivemind_core.protocol.LOG.warning") as warning,
    ):
        proto.touch_last_seen(first)
        proto.touch_last_seen(second)

    assert proto._last_seen_queue.put_nowait.call_count == 2, (
        "both touches must reach the saturated queue"
    )
    assert proto._last_seen_next_flush[first.key] == 40.0
    assert proto._last_seen_next_flush[second.key] == 40.0
    warning.assert_called_once_with("Dropping last_seen update because the queue is full")


def test_last_seen_worker_stops_after_draining_queue():
    user = SimpleNamespace(last_seen=0)
    db = FakeClientDatabase(user)
    proto = _protocol(db)
    proto._start_last_seen_worker()
    proto._last_seen_queue.put((_client(), 123.5))

    proto.shutdown()

    assert user.last_seen == 123.5
    assert proto._last_seen_thread is None
    assert not proto._last_seen_worker_started


def test_disconnect_keeps_debounce_cache_for_shared_key_sibling():
    proto = _protocol(FakeClientDatabase(SimpleNamespace(last_seen=0)))
    disconnected = _client(peer="peer-1")
    sibling = _client(peer="peer-2")
    proto.clients = {
        disconnected.peer: disconnected,
        sibling.peer: sibling,
    }
    proto._last_seen_next_flush["access-key"] = 100.0

    proto.handle_client_disconnected(disconnected)

    assert disconnected.peer not in proto.clients
    assert sibling.peer in proto.clients
    assert proto._last_seen_next_flush["access-key"] == 100.0
    disconnected.disconnect.assert_called_once_with()


def test_disconnect_clears_debounce_cache_after_last_key_peer_leaves():
    proto = _protocol(FakeClientDatabase(SimpleNamespace(last_seen=0)))
    disconnected = _client(peer="peer-1")
    other_key = _client(peer="peer-2", key="other-key")
    proto.clients = {
        disconnected.peer: disconnected,
        other_key.peer: other_key,
    }
    proto._last_seen_next_flush["access-key"] = 100.0
    proto._last_seen_next_flush["other-key"] = 101.0

    proto.handle_client_disconnected(disconnected)

    assert "access-key" not in proto._last_seen_next_flush
    assert proto._last_seen_next_flush["other-key"] == 101.0


def test_a_start_racing_shutdown_cannot_resurrect_the_worker():
    """Stop holds the lock start assigns under.

    `shutdown()` sets `_shutdown_requested` before stopping, and the start path
    refuses once that is set -- but a start that had already passed the check
    was still inside the lock assigning the thread and queue while stop ran.
    Stop could null them and then watch a worker appear behind it.
    """
    import threading

    proto = _protocol(FakeClientDatabase(SimpleNamespace(last_seen=0)))
    inside = threading.Event()
    release = threading.Event()
    real_thread_start = threading.Thread.start

    def _slow_start(self):
        if self.name == "hivemind-last-seen":
            inside.set()
            release.wait(5)
        return real_thread_start(self)

    with patch.object(threading.Thread, "start", _slow_start):
        starter = threading.Thread(target=proto._start_last_seen_worker)
        starter.start()
        assert inside.wait(5), "the start path never reached thread creation"

        stopped = threading.Event()

        def _stop():
            proto.shutdown()
            stopped.set()

        stopper = threading.Thread(target=_stop)
        stopper.start()
        # Stop must be waiting on the lock, not racing through it.
        assert not stopped.wait(0.2), "stop ran while start held the lock"
        release.set()
        starter.join(5)
        stopper.join(5)

    assert stopped.is_set()
    assert proto._last_seen_worker_started is False
    assert proto._last_seen_thread is None
    assert proto._last_seen_queue is None
