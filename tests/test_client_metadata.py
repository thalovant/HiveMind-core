import json
from stat import S_IMODE
from unittest.mock import patch

import pytest
from click import BadParameter
from click.testing import CliRunner

from hivemind_core.database import ClientDatabase
from hivemind_core.scripts import (
    add_client,
    blacklist_skill,
    delete_client,
    export_clients,
    list_clients,
    parse_client_metadata,
    print_config,
    set_metadata,
)


class MemoryDB:
    """Minimal AbstractDB stand-in for ClientDatabase tests."""

    def __init__(self):
        self.clients = []

    def search_by_value(self, key, value):
        return [c for c in self.clients if getattr(c, key, None) == value]

    def add_item(self, client):
        self.clients.append(client)
        return True

    def update_item(self, client):
        for i, c in enumerate(self.clients):
            if c.client_id == client.client_id:
                self.clients[i] = client
                return True
        self.clients.append(client)
        return True

    def delete_item(self, client):
        self.clients = [item for item in self.clients if item.client_id != client.client_id]
        return True

    def __len__(self):
        return len(self.clients)

    def __iter__(self):
        return iter(self.clients)


def make_client_db():
    db = object.__new__(ClientDatabase)
    db.db = MemoryDB()
    return db


# --- parse_client_metadata ---------------------------------------------------


def test_parse_metadata_accepts_json_object():
    assert parse_client_metadata('{"account_id":"acct_123"}') == {
        "account_id": "acct_123",
    }


def test_parse_metadata_accepts_empty_object():
    assert parse_client_metadata("{}") == {}


def test_parse_metadata_passes_through_none():
    assert parse_client_metadata(None) is None


def test_parse_metadata_rejects_empty_string():
    with pytest.raises(BadParameter):
        parse_client_metadata("")


def test_parse_metadata_rejects_malformed_json():
    with pytest.raises(BadParameter):
        parse_client_metadata("{")


def test_parse_metadata_rejects_top_level_array():
    with pytest.raises(BadParameter):
        parse_client_metadata('["account_id"]')


def test_parse_metadata_rejects_top_level_string():
    with pytest.raises(BadParameter):
        parse_client_metadata('"just-a-string"')


def test_parse_metadata_rejects_top_level_number():
    with pytest.raises(BadParameter):
        parse_client_metadata("42")


def test_parse_metadata_accepts_nested_structures():
    payload = '{"tags":["a","b"],"flags":{"premium":true}}'
    assert parse_client_metadata(payload) == {
        "tags": ["a", "b"],
        "flags": {"premium": True},
    }


# --- ClientDatabase.add_client metadata round-trip --------------------------


def test_add_client_persists_metadata():
    db = make_client_db()
    assert db.add_client(
        name="satellite",
        key="access-key",
        metadata={"account_id": "acct_123"},
    )
    client = db.get_client_by_api_key("access-key")
    assert client.metadata == {"account_id": "acct_123"}


def test_add_client_defaults_metadata_to_empty_dict():
    db = make_client_db()
    assert db.add_client(name="satellite", key="access-key")
    client = db.get_client_by_api_key("access-key")
    assert client.metadata == {}


def test_add_client_overwrites_metadata_on_existing_client():
    db = make_client_db()
    db.add_client(name="satellite", key="access-key", metadata={"account_id": "acct_123"})
    assert db.add_client(
        name="satellite",
        key="access-key",
        metadata={"account_id": "acct_456", "group": "standard"},
    )
    client = db.get_client_by_api_key("access-key")
    assert client.metadata == {"account_id": "acct_456", "group": "standard"}


def test_add_client_leaves_metadata_alone_when_not_provided_on_update():
    db = make_client_db()
    db.add_client(name="satellite", key="access-key", metadata={"account_id": "acct_123"})
    db.add_client(name="satellite-renamed", key="access-key")
    client = db.get_client_by_api_key("access-key")
    assert client.metadata == {"account_id": "acct_123"}
    assert client.name == "satellite-renamed"


def test_add_client_copies_metadata_dict():
    db = make_client_db()
    payload = {"account_id": "acct_123"}
    db.add_client(name="satellite", key="access-key", metadata=payload)
    payload["account_id"] = "mutated"
    client = db.get_client_by_api_key("access-key")
    assert client.metadata == {"account_id": "acct_123"}


# --- CLI end-to-end ----------------------------------------------------------


def _patched_db_ctx(fake_db):
    class _Ctx:
        def __enter__(self): return fake_db
        def __exit__(self, *a): return False
    return _Ctx()


def test_cli_add_client_with_metadata_flows_to_db():
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(
            add_client,
            [
                "--name", "satellite",
                "--access-key", "access-key",
                "--password", "pw", "--allow-weak-password",
                "--metadata", '{"account_id":"acct_123"}',
            ],
        )

    assert result.exit_code == 0, result.output
    client = fake_db.get_client_by_api_key("access-key")
    assert client.metadata == {"account_id": "acct_123"}
    assert "Metadata:" in result.output
    assert '"account_id": "acct_123"' in result.output


def test_cli_add_client_rejects_invalid_metadata_json():
    runner = CliRunner()
    result = runner.invoke(
        add_client,
        ["--name", "satellite", "--access-key", "k", "--password", "pw", "--allow-weak-password", "--metadata", "{"],
    )
    assert result.exit_code != 0
    assert "must be valid JSON" in result.output


def test_cli_add_client_rejects_metadata_top_level_array():
    runner = CliRunner()
    result = runner.invoke(
        add_client,
        ["--name", "satellite", "--access-key", "k", "--password", "pw", "--allow-weak-password", "--metadata", "[]"],
    )
    assert result.exit_code != 0
    assert "must be a JSON object" in result.output


def test_cli_add_client_without_metadata_omits_metadata_line():
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(
            add_client,
            ["--name", "satellite", "--access-key", "k", "--password", "pw", "--allow-weak-password"],
        )

    assert result.exit_code == 0, result.output
    assert "Metadata:" not in result.output


def test_cli_add_client_never_prints_plaintext_credentials():
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(
            add_client,
            ["--name", "satellite", "--access-key", "access-secret",
             "--password", "password-secret", "--allow-weak-password"],
        )

    assert result.exit_code == 0, result.output
    assert "access-secret" not in result.output
    assert "password-secret" not in result.output
    assert "<redacted>" in result.output


def test_cli_add_client_requires_private_file_for_generated_credentials(tmp_path):
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        missing = runner.invoke(add_client, ["--name", "satellite"])
        credentials_path = tmp_path / "client.json"
        created = runner.invoke(
            add_client,
            ["--name", "satellite", "--credentials-file", str(credentials_path)],
        )

    assert missing.exit_code != 0
    assert "--credentials-file is required" in missing.output
    assert created.exit_code == 0, created.output
    payload = json.loads(credentials_path.read_text())
    assert payload["access_key"]
    assert payload["password"]
    assert S_IMODE(credentials_path.stat().st_mode) == 0o600
    assert payload["access_key"] not in created.output
    assert payload["password"] not in created.output


def test_cli_client_listing_and_deletion_redact_credentials():
    runner = CliRunner()
    fake_db = make_client_db()
    fake_db.add_client(name="satellite", key="access-secret", password="password-secret",
                       crypto_key="crypto-secret")
    client = fake_db.get_client_by_api_key("access-secret")

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        listed = runner.invoke(list_clients)
        deleted = runner.invoke(delete_client, [str(client.client_id)])

    assert listed.exit_code == 0, listed.output
    assert deleted.exit_code == 0, deleted.output
    for output in (listed.output, deleted.output):
        assert "access-secret" not in output
        assert "password-secret" not in output
        assert "crypto-secret" not in output


def test_cli_print_config_redacts_nested_credentials():
    runner = CliRunner()
    config = {
        "database": {"redis": {"password": "redis-secret", "host": "redis"}},
        "token": "api-token",
    }
    with patch("hivemind_core.scripts.get_server_config", return_value=config):
        result = runner.invoke(print_config)

    assert result.exit_code == 0, result.output
    assert "redis-secret" not in result.output
    assert "api-token" not in result.output
    assert result.output.count("<redacted>") == 2


def test_cli_export_credentials_requires_private_new_file(tmp_path):
    runner = CliRunner()
    fake_db = make_client_db()
    fake_db.add_client(name="satellite", key="access-secret", password="password-secret",
                       crypto_key="crypto-secret")
    export_path = tmp_path / "clients.csv"

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        exported = runner.invoke(export_clients, ["--path", str(export_path)])
        overwrite = runner.invoke(export_clients, ["--path", str(export_path)])

    assert exported.exit_code == 0, exported.output
    assert S_IMODE(export_path.stat().st_mode) == 0o600
    text = export_path.read_text()
    assert "access-secret" in text
    assert "password-secret" in text
    assert "access-secret" not in exported.output
    assert overwrite.exit_code != 0
    assert "refusing to overwrite" in overwrite.output


# --- password-strength gate + derive-psk --------------------------------------


def test_cli_add_client_refuses_weak_password_by_default():
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(
            add_client,
            ["--name", "satellite", "--access-key", "k", "--password", "pw"],
        )

    assert result.exit_code != 0
    assert "--allow-weak-password" in result.output
    assert fake_db.get_client_by_api_key("k") is None


def test_cli_add_client_accepts_weak_password_with_override_flag():
    runner = CliRunner()
    fake_db = make_client_db()

    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(
            add_client,
            ["--name", "satellite", "--access-key", "k",
             "--password", "pw", "--allow-weak-password"],
        )

    assert result.exit_code == 0, result.output
    client = fake_db.get_client_by_api_key("k")
    assert client is not None
    assert client.password == "pw"


def test_cli_derive_psk_prints_hex_psk():
    from hivemind_core.scripts import derive_psk

    runner = CliRunner()
    result = runner.invoke(
        derive_psk,
        ["--password", "any-site-password", "--node-id", "test-node"],
    )
    assert result.exit_code == 0, result.output
    psk_hex = result.output.strip().splitlines()[-1]
    assert len(psk_hex) == 64
    assert set(psk_hex) <= set("0123456789abcdef")


# --- set-metadata + OVOS-policy blacklist commands ---------------------------


def _seed_client(fake_db, metadata=None):
    fake_db.add_client(name="sat", key="ak", metadata=metadata or {})
    return fake_db.get_client_by_api_key("ak")


def test_cli_set_metadata_merges_json_object():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db, {"account_id": "acct_1"})
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(set_metadata, [str(client.client_id), "--metadata", '{"tier":"pro"}'])
    assert result.exit_code == 0, result.output
    assert fake_db.get_client_by_api_key("ak").metadata == {"account_id": "acct_1", "tier": "pro"}


def test_cli_set_metadata_key_value_parses_json():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db)
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(set_metadata, [str(client.client_id), "--key", "skill_blacklist", "--value", '["skill-weather"]'])
    assert result.exit_code == 0, result.output
    assert fake_db.get_client_by_api_key("ak").metadata["skill_blacklist"] == ["skill-weather"]


def test_cli_set_metadata_value_falls_back_to_string():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db)
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(set_metadata, [str(client.client_id), "--key", "tier", "--value", "pro"])
    assert result.exit_code == 0, result.output
    assert fake_db.get_client_by_api_key("ak").metadata["tier"] == "pro"


def test_cli_set_metadata_unset_removes_key():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db, {"tier": "pro", "keep": 1})
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(set_metadata, [str(client.client_id), "--unset", "tier"])
    assert result.exit_code == 0, result.output
    assert fake_db.get_client_by_api_key("ak").metadata == {"keep": 1}


def test_cli_set_metadata_requires_an_argument():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db)
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(set_metadata, [str(client.client_id)])
    assert result.exit_code != 0


def test_cli_blacklist_skill_writes_metadata_without_deprecation():
    runner = CliRunner()
    fake_db = make_client_db()
    client = _seed_client(fake_db)
    with patch("hivemind_core.scripts.ClientDatabase", return_value=_patched_db_ctx(fake_db)):
        result = runner.invoke(blacklist_skill, ["skill-weather", str(client.client_id)])
    assert result.exit_code == 0, result.output
    assert "eprecat" not in result.output
    assert fake_db.get_client_by_api_key("ak").metadata["skill_blacklist"] == ["skill-weather"]
