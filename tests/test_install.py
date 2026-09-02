from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

import install


@contextmanager
def running_as_root() -> Iterator[None]:
    """Patch getuid only around install() so tmp_path setup stays unpatched."""
    with patch("os.getuid", return_value=0):
        yield


@contextmanager
def mocked_privileged_calls() -> Iterator[MagicMock]:
    """Capture chown/chmod without touching the filesystem ownership."""
    calls = MagicMock()
    with patch("os.chown", calls.chown), patch("os.chmod", calls.chmod):
        yield calls


@pytest.fixture
def source_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "set_dns.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return source


@pytest.fixture
def dispatcher_path(tmp_path):
    dispatcher_dir = tmp_path / "dispatcher.d"
    dispatcher_dir.mkdir()
    return dispatcher_dir / "set_dns"


class TestInstall:
    def test_requires_root(self):
        with patch("os.getuid", return_value=1000), pytest.raises(SystemExit):
            install.install()

    def test_missing_dispatcher_directory_fails(self, source_dir, tmp_path):
        missing_target = tmp_path / "missing" / "set_dns"

        with running_as_root(), pytest.raises(SystemExit):
            install.install(
                source_dir=source_dir,
                dispatcher_path=missing_target,
                config_files=(),
            )

    def test_preferred_config_wins_over_aliases(
        self, source_dir, dispatcher_path, tmp_path
    ):
        (source_dir / "cflan_vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        (source_dir / "vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        preferred_target = tmp_path / "cflan_vars.yaml"
        legacy_target = tmp_path / "vars.yaml"

        with running_as_root(), mocked_privileged_calls():
            install.install(
                source_dir=source_dir,
                dispatcher_path=dispatcher_path,
                config_files=(
                    ("cflan_vars.yaml", str(preferred_target)),
                    ("vars.yaml", str(legacy_target)),
                ),
            )

        assert dispatcher_path.is_file()
        assert preferred_target.is_file()
        assert not legacy_target.exists()

    def test_legacy_config_mapping_remains_valid(
        self, source_dir, dispatcher_path, tmp_path
    ):
        (source_dir / "vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        legacy_target = tmp_path / "vars.yaml"

        with running_as_root(), mocked_privileged_calls():
            install.install(
                source_dir=source_dir,
                dispatcher_path=dispatcher_path,
                config_files=(
                    ("cflan_vars.yaml", str(tmp_path / "cflan_vars.yaml")),
                    ("vars.yaml", str(legacy_target)),
                ),
            )

        assert legacy_target.is_file()

    def test_installer_reports_targets_with_expected_ownership_and_modes(
        self, source_dir, dispatcher_path, tmp_path, capsys
    ):
        (source_dir / "cflan_vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        config_target = tmp_path / "cflan_vars.yaml"

        with running_as_root(), mocked_privileged_calls() as privileged_calls:
            install.install(
                source_dir=source_dir,
                dispatcher_path=dispatcher_path,
                config_files=(("cflan_vars.yaml", str(config_target)),),
            )

        privileged_calls.chown.assert_any_call(dispatcher_path, 0, 0)
        privileged_calls.chown.assert_any_call(config_target, 0, 0)
        privileged_calls.chmod.assert_any_call(dispatcher_path, 0o700)
        privileged_calls.chmod.assert_any_call(config_target, 0o600)
        output = capsys.readouterr().out
        assert f"Installed: {dispatcher_path}" in output
        assert f"Installed: {config_target}" in output

    def test_missing_config_warns_without_installing_one(
        self, source_dir, dispatcher_path, capsys
    ):
        with running_as_root(), mocked_privileged_calls() as privileged_calls:
            install.install(
                source_dir=source_dir,
                dispatcher_path=dispatcher_path,
                config_files=(("cflan_vars.yaml", "/should-not-be-used"),),
            )

        output = capsys.readouterr().out
        assert "Warning: No configuration file found." in output
        assert privileged_calls.chmod.call_count == 1
