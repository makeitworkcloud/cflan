"""Tests for the set_dns module."""

import socket
import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Mock netifaces before import
sys.modules["netifaces"] = MagicMock()
sys.modules["CloudFlare"] = MagicMock()
sys.modules["yaml"] = MagicMock()

from set_dns import (  # noqa: E402
    create_dns_record,
    get_dns_record_id,
    get_local_ip,
    get_yaml_vars,
    get_zone_info,
    update_dns_record,
    validate_network_manager_args,
)


class TestGetLocalIp:
    """Tests for get_local_ip function."""

    @patch("set_dns.socket.gethostbyname")
    @patch("set_dns.socket.gethostname")
    def test_get_local_ip_with_local_suffix(self, mock_hostname, mock_gethost):
        """Test getting local IP with .local suffix."""
        mock_hostname.return_value = "testhost"
        mock_gethost.return_value = "192.168.1.100"
        result = get_local_ip()
        assert result == "192.168.1.100"
        mock_gethost.assert_any_call("testhost.local")

    @patch("set_dns.socket.gethostbyname")
    @patch("set_dns.socket.gethostname")
    def test_get_local_ip_fallback_to_lan(self, mock_hostname, mock_gethost):
        """Test fallback to .lan suffix when .local fails."""
        mock_hostname.return_value = "testhost"

        def side_effect(hostname):
            if hostname.endswith(".local"):
                raise socket.gaierror("Not found")
            return "192.168.1.100"

        mock_gethost.side_effect = side_effect
        result = get_local_ip()
        assert result == "192.168.1.100"

    @patch("set_dns.socket.gethostbyname")
    @patch("set_dns.socket.gethostname")
    def test_get_local_ip_both_suffixes_fail(self, mock_hostname, mock_gethost):
        """Test that exception propagates when both .local and .lan fail."""
        mock_hostname.return_value = "testhost"

        def side_effect(hostname):
            raise socket.gaierror("Not found")

        mock_gethost.side_effect = side_effect

        with pytest.raises(socket.gaierror):
            get_local_ip()


class TestValidateNetworkManagerArgs:
    """Tests for validate_network_manager_args function."""

    @patch("set_dns.netifaces")
    @patch("set_dns.sys")
    def test_valid_interface_and_action(self, mock_sys, mock_netifaces):
        """Test validation passes with correct interface and action."""
        mock_sys.argv = ["script", "eth0", "up"]
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "192.168.1.100"}]}
        mock_netifaces.AF_INET = 2

        # Should not raise or exit
        validate_network_manager_args("192.168.1.100")

    @patch("set_dns.netifaces")
    @patch("set_dns.sys")
    def test_mismatched_ip_address(self, mock_sys, mock_netifaces):
        """Test validation fails when IP doesn't match."""
        mock_sys.argv = ["script", "eth0", "up"]
        mock_sys.exit.side_effect = SystemExit
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "10.0.0.1"}]}
        mock_netifaces.AF_INET = 2

        with pytest.raises(SystemExit):
            validate_network_manager_args("192.168.1.100")

    @patch("set_dns.netifaces")
    @patch("set_dns.sys")
    def test_wrong_action(self, mock_sys, mock_netifaces):
        """Test validation fails with wrong action."""
        mock_sys.argv = ["script", "eth0", "down"]
        mock_sys.exit.side_effect = SystemExit
        mock_netifaces.ifaddresses.return_value = {2: [{"addr": "192.168.1.100"}]}
        mock_netifaces.AF_INET = 2

        with pytest.raises(SystemExit):
            validate_network_manager_args("192.168.1.100")

    @patch("set_dns.netifaces")
    @patch("set_dns.sys")
    def test_no_arguments(self, mock_sys, mock_netifaces):
        """Test validation continues when no arguments provided."""
        mock_sys.argv = ["script"]
        mock_netifaces.AF_INET = 2

        # Should not raise
        validate_network_manager_args("192.168.1.100")


class TestGetYamlVars:
    """Tests for get_yaml_vars function."""

    @patch(
        "builtins.open",
        mock_open(read_data="cf_token: test123\ncf_domain: example.com"),
    )
    @patch("set_dns.yaml")
    def test_get_unencrypted_yaml(self, mock_yaml):
        """Test reading unencrypted vars.yaml."""
        mock_yaml.safe_load.return_value = {
            "cf_token": "test123",
            "cf_domain": "example.com",
        }

        result = get_yaml_vars()

        assert result["cf_token"] == "test123"
        assert result["cf_domain"] == "example.com"

    @patch("set_dns.subprocess.run")
    @patch("set_dns.yaml")
    @patch("builtins.open")
    def test_get_sops_encrypted_yaml(self, mock_open_file, mock_yaml, mock_run):
        """Test reading sops encrypted yaml when vars.yaml missing."""
        # First open raises FileNotFoundError
        mock_open_file.side_effect = FileNotFoundError()

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"cf_token: encrypted123\ncf_domain: example.com",
            stderr=b"",
        )
        mock_yaml.safe_load.return_value = {
            "cf_token": "encrypted123",
            "cf_domain": "example.com",
        }

        result = get_yaml_vars()

        assert result["cf_token"] == "encrypted123"
        mock_run.assert_called_once()

    @patch("set_dns.subprocess.run")
    @patch("builtins.open")
    def test_sops_not_installed(self, mock_open_file, mock_run):
        """Test exit when sops is not installed."""
        mock_open_file.side_effect = FileNotFoundError()
        mock_run.side_effect = FileNotFoundError("sops not found")

        with pytest.raises(SystemExit):
            get_yaml_vars()


class TestGetZoneInfo:
    """Tests for get_zone_info function."""

    def test_get_zone_info(self):
        """Test retrieving zone ID and name."""
        mock_cf = MagicMock()
        mock_cf.zones.get.return_value = [{"id": "zone123", "name": "example.com"}]

        zone_id, zone_name = get_zone_info(mock_cf, "example.com")

        assert zone_id == "zone123"
        assert zone_name == "example.com"


class TestGetDnsRecordId:
    """Tests for get_dns_record_id function."""

    def test_existing_record_found(self):
        """Test getting DNS record ID when record exists."""
        mock_cf = MagicMock()
        mock_cf.zones.dns_records.get.return_value = [{"id": "record123"}]

        result = get_dns_record_id(mock_cf, "zone123", "host", "example.com")

        assert result == "record123"

    def test_no_existing_record(self):
        """Test empty string returned when no record exists."""
        mock_cf = MagicMock()
        mock_cf.zones.dns_records.get.return_value = []

        result = get_dns_record_id(mock_cf, "zone123", "host", "example.com")

        assert result == ""


class TestCreateDnsRecord:
    """Tests for create_dns_record function."""

    def test_create_record_success(self):
        """Test successful DNS record creation."""
        mock_cf = MagicMock()

        create_dns_record(mock_cf, "zone123", "host", "192.168.1.100")

        mock_cf.zones.dns_records.post.assert_called_once_with(
            "zone123",
            data={"name": "host", "type": "A", "content": "192.168.1.100"},
        )

    def test_create_record_api_error(self):
        """Test handling of Cloudflare API error."""
        mock_cf = MagicMock()

        # Create a proper exception class that inherits from Exception
        class MockAPIError(Exception):
            def __str__(self):
                return "API Error"

            def __int__(self):
                return 400

        mock_cf.zones.dns_records.post.side_effect = MockAPIError("API Error")
        # Also set the exception on the module mock so isinstance check passes
        import sys

        sys.modules["CloudFlare"].exceptions.CloudFlareAPIError = MockAPIError

        with pytest.raises(SystemExit):
            create_dns_record(mock_cf, "zone123", "host", "192.168.1.100")


class TestUpdateDnsRecord:
    """Tests for update_dns_record function."""

    def test_update_when_ip_changed(self):
        """Test updating record when IP has changed."""
        mock_cf = MagicMock()
        mock_cf.zones.dns_records.get.return_value = [{"content": "10.0.0.1"}]

        update_dns_record(
            mock_cf, "zone123", "record123", "host.example.com", "192.168.1.100"
        )

        mock_cf.zones.dns_records.delete.assert_called_once_with("zone123", "record123")
        mock_cf.zones.dns_records.post.assert_called_once()

    def test_no_update_when_ip_unchanged(self):
        """Test exiting when IP hasn't changed."""
        mock_cf = MagicMock()
        mock_cf.zones.dns_records.get.return_value = [{"content": "192.168.1.100"}]

        with pytest.raises(SystemExit):
            update_dns_record(
                mock_cf, "zone123", "record123", "host.example.com", "192.168.1.100"
            )
