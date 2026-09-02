from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest

import set_dns


@pytest.fixture
def config_values():
    return {
        "cf_token": "test-token",
        "cf_domain_name": "example.com",
    }


class TestAddresses:
    @patch("set_dns.socket.gethostbyname")
    @patch("set_dns.socket.gethostname", return_value="testhost")
    def test_get_local_ip_prefers_local_name(self, _, mock_gethost):
        mock_gethost.return_value = "192.168.1.100"

        assert set_dns.get_local_ip() == "192.168.1.100"
        mock_gethost.assert_called_once_with("testhost.local")

    @patch("set_dns.socket.gethostbyname")
    @patch("set_dns.socket.gethostname", return_value="testhost")
    def test_get_local_ip_falls_back_to_lan_name(self, _, mock_gethost):
        mock_gethost.side_effect = [OSError("missing"), "192.168.1.100"]

        assert set_dns.get_local_ip() == "192.168.1.100"
        assert mock_gethost.call_args_list[1].args == ("testhost.lan",)

    @pytest.mark.parametrize(
        "value", ["127.0.0.1", "0.0.0.0", "224.0.0.1", "not-an-ip"]
    )
    def test_validate_ipv4_rejects_unsuitable_addresses(self, value):
        with pytest.raises(set_dns.CflanError):
            set_dns.validate_ipv4(value)


class TestNetworkManagerArguments:
    def test_valid_interface_and_action(self, monkeypatch):
        mock_netifaces = MagicMock()
        mock_netifaces.AF_INET = 2
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "192.168.1.100"}]}
        monkeypatch.setattr(set_dns, "netifaces", mock_netifaces)

        assert set_dns.validate_network_manager_args(
            "192.168.1.100", ["set_dns", "eth0", "up"]
        )

    def test_non_up_action_is_skipped(self):
        assert not set_dns.validate_network_manager_args(
            "192.168.1.100", ["set_dns", "eth0", "down"]
        )

    def test_mismatched_interface_address_is_rejected(self, monkeypatch):
        mock_netifaces = MagicMock()
        mock_netifaces.AF_INET = 2
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "10.0.0.1"}]}
        monkeypatch.setattr(set_dns, "netifaces", mock_netifaces)

        with pytest.raises(set_dns.CflanError):
            set_dns.validate_network_manager_args(
                "192.168.1.100", ["set_dns", "eth0", "up"]
            )


class TestConfiguration:
    def test_prefers_cflan_prefixed_root_volume_filename(self, tmp_path):
        preferred = tmp_path / "cflan_vars.yaml"
        legacy = tmp_path / "vars.yaml"
        preferred.write_text("cf_token: test-token\ncf_domain_name: example.com\n")
        legacy.write_text("cf_token: test-token\ncf_domain_name: example.com\n")

        path, encrypted = set_dns.resolve_config_path(
            config_paths=((preferred, False), (legacy, False))
        )

        assert path == preferred
        assert not encrypted

    def test_legacy_root_volume_filename_remains_an_alias(self, tmp_path):
        legacy = tmp_path / "vars.yaml"
        legacy.write_text("cf_token: test-token\ncf_domain_name: example.com\n")

        path, encrypted = set_dns.resolve_config_path(config_paths=((legacy, False),))

        assert path == legacy
        assert not encrypted

    @patch(
        "builtins.open",
        mock_open(read_data="cf_token: test-token\ncf_domain_name: example.com"),
    )
    @patch(
        "set_dns.Path.read_text",
        return_value="cf_token: test-token\ncf_domain_name: example.com",
    )
    def test_reads_plaintext_yaml(self, mock_read):
        values = set_dns.read_config_file(Path("/cflan_vars.yaml"), encrypted=False)

        assert values["cf_token"] == "test-token"
        mock_read.assert_called_once_with(encoding="utf-8")

    @patch("set_dns.subprocess.run")
    def test_reads_sops_yaml_without_writing_plaintext(self, mock_run):
        mock_run.return_value.stdout = (
            "cf_token: test-token\ncf_domain_name: example.com"
        )

        values = set_dns.read_config_file(Path("/cflan_sops_vars.yaml"), encrypted=True)

        assert values["cf_domain_name"] == "example.com"
        mock_run.assert_called_once()

    def test_config_requires_token_and_domain(self):
        with pytest.raises(set_dns.CflanError):
            set_dns.parse_config({"cf_token": "test-token"})

    def test_config_rejects_invalid_ttl(self, config_values):
        config_values["cf_ttl"] = 30

        with pytest.raises(set_dns.CflanError):
            set_dns.parse_config(config_values)

    @patch("set_dns.socket.gethostname", return_value="host")
    def test_record_name_defaults_to_hostname(self, _, config_values):
        config = set_dns.parse_config(config_values)

        assert set_dns.get_record_name(config) == "host.example.com"


class TestCloudflareReconciliation:
    def test_get_zone_info_requires_exact_match(self):
        client = MagicMock()
        client.zones.list.return_value = [
            SimpleNamespace(id="zone-id", name="example.com")
        ]

        assert set_dns.get_zone_info(client, "example.com") == (
            "zone-id",
            "example.com",
        )

    def test_get_dns_record_rejects_duplicates(self):
        client = MagicMock()
        client.dns.records.list.return_value = [MagicMock(), MagicMock()]

        with pytest.raises(set_dns.CflanError):
            set_dns.get_dns_record(client, "zone-id", "host.example.com")

    def test_create_record_uses_explicit_defaults(self, config_values):
        client = MagicMock()
        config = set_dns.parse_config(config_values)

        set_dns.create_dns_record(
            client, "zone-id", "host.example.com", "192.168.1.100", config
        )

        client.dns.records.create.assert_called_once_with(
            zone_id="zone-id",
            name="host.example.com",
            type="A",
            content="192.168.1.100",
            ttl=1,
            proxied=False,
        )

    def test_update_record_uses_patch_without_delete(self):
        client = MagicMock()
        record = SimpleNamespace(
            id="record-id",
            content="10.0.0.1",
            ttl=300,
            proxied=True,
        )

        set_dns.update_dns_record(
            client,
            "zone-id",
            record,
            "host.example.com",
            "192.168.1.100",
        )

        client.dns.records.edit.assert_called_once_with(
            "record-id",
            zone_id="zone-id",
            name="host.example.com",
            type="A",
            content="192.168.1.100",
            ttl=300,
            proxied=True,
        )
        client.dns.records.delete.assert_not_called()

    def test_matching_record_is_not_mutated(self):
        client = MagicMock()
        record = SimpleNamespace(
            id="record-id",
            content="192.168.1.100",
            ttl=1,
            proxied=False,
        )

        set_dns.update_dns_record(
            client,
            "zone-id",
            record,
            "host.example.com",
            "192.168.1.100",
        )

        client.dns.records.edit.assert_not_called()


class TestDryRun:
    @pytest.fixture
    def config_file(self, tmp_path):
        path = tmp_path / "cflan_vars.yaml"
        path.write_text(
            "cf_token: test-token\ncf_domain_name: example.com\n", encoding="utf-8"
        )
        return path

    @patch("set_dns.Cloudflare")
    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_avoids_client_construction(
        self, _, __, mock_cloudflare, config_file, capsys
    ):
        assert set_dns.main(["set_dns", "--dry-run", "--config", str(config_file)]) == 0

        mock_cloudflare.assert_not_called()
        assert "no Cloudflare client" in capsys.readouterr().out

    @patch("set_dns.set_dns")
    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_never_enters_reconciliation(
        self, _, __, mock_set_dns, config_file
    ):
        assert set_dns.main(["set_dns", "--dry-run", "--config", str(config_file)]) == 0

        mock_set_dns.assert_not_called()

    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_reports_intended_action(self, _, __, config_file, capsys):
        assert set_dns.main(["set_dns", "--dry-run", "--config", str(config_file)]) == 0

        output = capsys.readouterr().out
        assert "would reconcile A record" in output
        assert "host.example.com" in output
        assert "192.168.1.100" in output
        assert "test-token" not in output

    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_config_override_reaches_config_selection(self, _, __, config_file, capsys):
        assert set_dns.main(["set_dns", "--dry-run", "--config", str(config_file)]) == 0

        assert str(config_file) in capsys.readouterr().out

    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_rejects_invalid_config(self, _, __, tmp_path):
        bad_config = tmp_path / "cflan_vars.yaml"
        bad_config.write_text("cf_domain_name: example.com\n", encoding="utf-8")

        assert set_dns.main(["set_dns", "--dry-run", "--config", str(bad_config)]) == 1

    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_preserves_dispatcher_arguments(
        self, _, __, monkeypatch, config_file
    ):
        mock_netifaces = MagicMock()
        mock_netifaces.AF_INET = 2
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "192.168.1.100"}]}
        monkeypatch.setattr(set_dns, "netifaces", mock_netifaces)

        assert (
            set_dns.main(
                ["set_dns", "eth0", "up", "--dry-run", "--config", str(config_file)]
            )
            == 0
        )
        mock_netifaces.ifaddresses.assert_called_once_with("eth0")

    @patch("set_dns.socket.gethostbyname", return_value="192.168.1.100")
    @patch("set_dns.socket.gethostname", return_value="host")
    def test_dry_run_skips_non_up_dispatcher_action(self, _, __, config_file, capsys):
        assert (
            set_dns.main(
                ["set_dns", "eth0", "down", "--dry-run", "--config", str(config_file)]
            )
            == 0
        )

        output = capsys.readouterr().out
        assert "Skipping NetworkManager action" in output
        assert "would reconcile" not in output


class TestEntrypoint:
    @patch("set_dns.set_dns", side_effect=set_dns.CflanError("bad configuration"))
    def test_main_returns_nonzero_for_expected_failure(self, _):
        assert set_dns.main(["set_dns"]) == 1

    @patch("set_dns.set_dns", side_effect=RuntimeError("unexpected"))
    def test_main_does_not_render_unexpected_error_text(self, _):
        assert set_dns.main(["set_dns"]) == 1
