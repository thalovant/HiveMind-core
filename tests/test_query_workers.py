import threading
import time
from concurrent.futures import Future
from types import SimpleNamespace

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_core.policy import PolicyChain
from hivemind_core.protocol import HiveMindListenerProtocol
from hivemind_plugin_manager.protocols import ClientCallbacks
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session


class _Bus:
    def __init__(self):
        self.messages = []

    def emit(self, message):
        self.messages.append(message)


class _Agent:
    callbacks = ClientCallbacks()

    def __init__(self, delay=0.05):
        self.bus = _Bus()
        self.delay = delay
        self.started = []
        self.lock = threading.Lock()
        self.hm_protocol = None

    def get_bus(self, _client=None):
        return self.bus

    def answer_query(self, utterance, _lang, client=None):
        with self.lock:
            self.started.append((utterance, time.monotonic()))
        time.sleep(self.delay)
        yield f"answer {utterance}"


class _BlockingAgent(_Agent):
    def __init__(self):
        super().__init__(delay=0)
        self.started_event = threading.Event()
        self.release_event = threading.Event()

    def answer_query(self, utterance, _lang, client=None):
        self.started_event.set()
        self.release_event.wait(1)
        yield f"answer {utterance}"


class _NoAnswerAgent(_Agent):
    def answer_query(self, utterance, _lang, client=None):
        yield None


class _FailingAgent(_Agent):
    def answer_query(self, utterance, _lang, client=None):
        raise RuntimeError("runtime delivery failed")
        yield


class _ContextAwareAgent(_Agent):
    def __init__(self):
        super().__init__(delay=0)
        self.admitted = None
        self.client = None

    def answer_query_message(self, message, client=None):
        self.admitted = message
        self.client = client
        yield "context-aware answer"

    def answer_query(self, _utterance, _lang, client=None):
        raise AssertionError("legacy answer_query path should not be called")


class _ProvenanceAgent(_ContextAwareAgent):
    def answer_query_message(self, message, client=None):
        self.admitted = message
        self.client = client
        yield Message(
            "ovos.utterance.speak",
            {"utterance": "owned answer"},
            {
                "query_id": "agent-internal-query",
                "skill_id": "answer.skill",
                "session": {
                    "session_id": "agent-internal-query",
                    "blacklisted_skills": ["must-not-leak"],
                },
            },
        )


class _BinaryProtocol:
    callbacks = ClientCallbacks()
    hm_protocol = None


class _Client:
    key = "client-key"
    crypto_key = "preshared"
    pswd_handshake = None
    binarize = False
    can_escalate = True
    site_id = "site"
    sent = None
    disconnected = False
    handshake = SimpleNamespace(pubkey="client-public-key")

    def __init__(self, name="client"):
        self.name = name
        self.sess = Session(session_id=f"{name}-session")

    @property
    def peer(self):
        return f"{self.name}::{self.sess.session_id}"

    def send(self, message):
        if self.sent is None:
            self.sent = []
        self.sent.append(message)

    def disconnect(self):
        self.disconnected = True

    def authorize(self, _message):
        return True


class _ConfirmedClient(_Client):
    def __init__(self, name="client"):
        super().__init__(name=name)
        self.delivery_started = threading.Event()
        self.delivery = Future()

    def send(self, message):
        super().send(message)
        inner = getattr(getattr(message, "payload", None), "payload", None)
        if getattr(inner, "msg_type", None) == "speak":
            self.delivery_started.set()
            return self.delivery
        return None


def _protocol(monkeypatch, agent=None, config=None):
    server_config = {"min_protocol_version": 0, **(config or {})}
    monkeypatch.setattr(
        "hivemind_core.protocol.get_server_config",
        lambda: server_config,
    )
    proto = HiveMindListenerProtocol(
        agent_protocol=agent or _Agent(),
        binary_data_protocol=_BinaryProtocol(),
        identity=SimpleNamespace(private_key="private", site_id="master-site"),
        db=SimpleNamespace(),
    )
    proto.policy_chain = PolicyChain()
    proto.peer = "master"
    return proto


def _request(query_id, text):
    inner = HiveMessage(
        HiveMessageType.BUS,
        payload=Message("recognizer_loop:utterance", {"utterances": [text]}),
    )
    return HiveMessage(
        HiveMessageType.QUERY,
        payload=inner,
        metadata={"query_id": query_id},
    )


def _wait_for_messages(client, count, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.sent is not None and len(client.sent) >= count:
            return client.sent
        time.sleep(0.01)
    return client.sent or []


def test_query_requests_run_concurrently(monkeypatch):
    agent = _Agent(delay=0.15)
    proto = _protocol(monkeypatch, agent=agent)
    client1 = _Client()
    client2 = _Client(name="client2")

    try:
        proto.handle_query_message(_request("q1", "one"), client1)
        proto.handle_query_message(_request("q2", "two"), client2)

        assert len(_wait_for_messages(client1, 2)) == 2
        assert len(_wait_for_messages(client2, 2)) == 2
        assert len(agent.started) == 2
        start_times = [started_at for _, started_at in agent.started]
        assert max(start_times) - min(start_times) < agent.delay
    finally:
        proto.shutdown()


def test_connection_hot_path_uses_startup_config_snapshot(monkeypatch):
    proto = _protocol(monkeypatch, config={
        "binarize": True,
        "allowed_ciphers": ["AES-GCM"],
        "allowed_encodings": ["json"],
    })
    client = _Client()
    monkeypatch.setattr(
        "hivemind_core.protocol.get_server_config",
        lambda: (_ for _ in ()).throw(
            AssertionError("connection hot path re-read server config")
        ),
    )

    try:
        proto.handle_new_client(client)

        assert len(client.sent) == 2
        assert client.sent[0].msg_type == HiveMessageType.HELLO
        assert client.sent[1].msg_type == HiveMessageType.HANDSHAKE
        assert client.sent[1].payload["binarize"] is True
    finally:
        proto.shutdown()


def test_connection_queues_handshake_before_blocking_presence_emit(monkeypatch):
    proto = _protocol(monkeypatch)
    client = _Client()
    presence_started = threading.Event()
    release_presence = threading.Event()

    def blocking_emit(_message):
        presence_started.set()
        release_presence.wait(1)

    proto.agent_protocol.bus.emit = blocking_emit
    worker = threading.Thread(target=proto.handle_new_client, args=(client,))
    worker.start()

    try:
        assert presence_started.wait(1)
        assert client.sent is not None
        assert [message.msg_type for message in client.sent] == [
            HiveMessageType.HELLO,
            HiveMessageType.HANDSHAKE,
        ]
    finally:
        release_presence.set()
        worker.join(1)
        proto.shutdown()

    assert not worker.is_alive()


def test_connection_queues_handshake_before_blocking_lifecycle_callback(monkeypatch):
    proto = _protocol(monkeypatch)
    client = _Client()
    callback_started = threading.Event()
    release_callback = threading.Event()

    def blocking_callback(_client):
        callback_started.set()
        release_callback.wait(1)

    proto.callbacks.on_connect = blocking_callback
    worker = threading.Thread(target=proto.handle_new_client, args=(client,))
    worker.start()

    try:
        assert callback_started.wait(1)
        assert client.sent is not None
        assert [message.msg_type for message in client.sent] == [
            HiveMessageType.HELLO,
            HiveMessageType.HANDSHAKE,
        ]
        assert proto.agent_protocol.bus.messages == []
    finally:
        release_callback.set()
        worker.join(1)
        proto.shutdown()

    assert not worker.is_alive()


def test_connection_protocol_admission_excludes_blocking_lifecycle_work(monkeypatch):
    proto = _protocol(monkeypatch)
    client = _Client()
    callback_started = threading.Event()
    release_callback = threading.Event()
    worker = None

    def blocking_callback(_client):
        callback_started.set()
        release_callback.wait(1)

    proto.callbacks.on_connect = blocking_callback

    try:
        assert proto.handle_new_client_protocol(client) is True
        assert not callback_started.is_set()
        assert [message.msg_type for message in client.sent] == [
            HiveMessageType.HELLO,
            HiveMessageType.HANDSHAKE,
        ]

        worker = threading.Thread(
            target=proto.handle_client_connected,
            args=(client,),
        )
        worker.start()
        assert callback_started.wait(1)
        assert proto.agent_protocol.bus.messages == []
    finally:
        release_callback.set()
        if worker is not None:
            worker.join(1)
        proto.shutdown()

    assert worker is not None and not worker.is_alive()


def test_query_hands_admitted_message_to_context_aware_agent(monkeypatch):
    agent = _ContextAwareAgent()
    proto = _protocol(monkeypatch, agent=agent)
    client = _Client()
    client.sess.site_id = "customer-site"
    client.sess.blacklisted_skills = ["blocked.skill"]

    try:
        proto.handle_query_message(_request("q-context", "hello"), client)

        assert len(_wait_for_messages(client, 2)) == 2
        assert agent.client is client
        assert agent.admitted is not None
        assert agent.admitted.context["destination"] == "skills"
        assert agent.admitted.context["source"] == client.peer
        assert agent.admitted.context["session"]["session_id"] == (
            client.sess.session_id
        )
        assert agent.admitted.context["session"]["site_id"] == "customer-site"
        assert agent.admitted.context["session"]["blacklisted_skills"] == [
            "blocked.skill"
        ]
    finally:
        proto.shutdown()


def test_query_response_preserves_only_safe_skill_provenance(monkeypatch):
    agent = _ProvenanceAgent()
    proto = _protocol(monkeypatch, agent=agent)
    client = _Client()

    try:
        proto.handle_query_message(_request("q-provenance", "hello"), client)

        sent = _wait_for_messages(client, 2)
        assert len(sent) == 2
        response = sent[0].payload.payload
        assert response.msg_type == "speak"
        assert response.data["utterance"] == "owned answer"
        assert response.data["lang"] == "en-US"
        assert response.context == {
            "query_id": "q-provenance",
            "session": {"session_id": "q-provenance"},
            "skill_id": "answer.skill",
        }
    finally:
        proto.shutdown()


def test_query_stream_waits_for_confirmed_reply_delivery(monkeypatch):
    proto = _protocol(monkeypatch, agent=_ContextAwareAgent())
    client = _ConfirmedClient()

    try:
        proto.handle_query_message(_request("q-delivery", "hello"), client)

        assert client.delivery_started.wait(1)
        assert len(client.sent) == 1
        client.delivery.set_result(None)

        assert len(_wait_for_messages(client, 2)) == 2
    finally:
        if not client.delivery.done():
            client.delivery.set_result(None)
        proto.shutdown()


def test_query_capacity_is_loaded_from_server_config(monkeypatch):
    proto = _protocol(
        monkeypatch,
        config={"query_workers": "2", "query_queue_size": "3"},
    )
    try:
        assert proto.query_workers == 2
        assert proto.query_queue_size == 3
    finally:
        proto.shutdown()


def test_query_worker_pool_returns_busy_when_saturated(monkeypatch):
    agent = _BlockingAgent()
    proto = _protocol(monkeypatch, agent=agent)
    proto.query_workers = 1
    proto.query_queue_size = 0
    client1 = _Client()
    client2 = _Client(name="client2")

    try:
        proto.handle_query_message(_request("q1", "one"), client1)
        assert agent.started_event.wait(1)

        proto.handle_query_message(_request("q2", "two"), client2)

        sent = _wait_for_messages(client2, 2)
        assert len(sent) == 2
        assert sent[0].payload.payload.data["error"] == "busy"
        assert sent[1].payload.payload.msg_type == "hive.query.complete"
        agent.release_event.set()
        assert len(_wait_for_messages(client1, 2)) == 2
    finally:
        agent.release_event.set()
        proto.shutdown()


def test_query_no_answer_always_terminates_the_response_stream(monkeypatch):
    proto = _protocol(monkeypatch, agent=_NoAnswerAgent())
    client = _Client()

    try:
        proto.handle_query_message(_request("q-no-answer", "hello"), client)

        sent = _wait_for_messages(client, 2)
        assert len(sent) == 2
        assert sent[0].payload.payload.msg_type == "hive.query.timeout"
        assert sent[0].payload.payload.data["error"] == "no_answer"
        assert sent[1].payload.payload.msg_type == "hive.query.complete"
    finally:
        proto.shutdown()


def test_query_worker_error_always_terminates_the_response_stream(monkeypatch):
    proto = _protocol(monkeypatch, agent=_FailingAgent())
    client = _Client()

    try:
        proto.handle_query_message(_request("q-error", "hello"), client)

        sent = _wait_for_messages(client, 2)
        assert len(sent) == 2
        assert sent[0].payload.payload.msg_type == "hive.query.timeout"
        assert sent[0].payload.payload.data["error"] == "internal"
        assert sent[1].payload.payload.msg_type == "hive.query.complete"
    finally:
        proto.shutdown()


def test_shutdown_rejects_new_query_work(monkeypatch):
    proto = _protocol(monkeypatch)
    client = _Client()

    proto.shutdown()
    proto.handle_query_message(_request("q-stop", "one"), client)

    sent = _wait_for_messages(client, 2)
    assert len(sent) == 2
    assert sent[0].payload.payload.data["error"] == "busy"
    assert sent[1].payload.payload.msg_type == "hive.query.complete"
    assert proto._query_executor is None
    assert not proto._query_workers_started
