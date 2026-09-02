from unittest.mock import MagicMock

import pytest

import install


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


@pytest.fixture
def as_root(monkeypatch):
    monkeypatch.setattr("os.getuid", lambda: 0)


@pytest.fixture
def privileged_calls(monkeypatch):
    calls = MagicMock()
    monkeypatch.setattr("os.chown", calls.chown)
    monkeypatch.setattr("os.chmod", calls.chmod)
    return calls


class TestInstall:
    def test_requires_root(self, monkeypatch):
        monkeypatch.setattr("os.getuid", lambda: 1000)

        with pytest.raises(SystemExit):
            install.install()

    def test_missing_dispatcher_directory_fails(self, as_root, source_dir, tmp_path):
        missing_target = tmp_path / "missing" / "set_dns"

        with pytest.raises(SystemExit):
            install.install(
                source_dir=source_dir,
                dispatcher_path=missing_target,
                config_files=(),
            )

    def test_preferred_config_wins_over_aliases(
        self, as_root, privileged_calls, source_dir, dispatcher_path, tmp_path
    ):
        (source_dir / "cflan_vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        (source_dir / "vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        preferred_target = tmp_path / "cflan_vars.yaml"
        legacy_target = tmp_path / "vars.yaml"

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
        self, as_root, privileged_calls, source_dir, dispatcher_path, tmp_path
    ):
        (source_dir / "vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        legacy_target = tmp_path / "vars.yaml"

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
        self,
        as_root,
        privileged_calls,
        source_dir,
        dispatcher_path,
        tmp_path,
        capsys,
    ):
        (source_dir / "cflan_vars.yaml").write_text(
            "cf_token: test-token\n", encoding="utf-8"
        )
        config_target = tmp_path / "cflan_vars.yaml"

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
        self, as_root, privileged_calls, source_dir, dispatcher_path, capsys
    ):
        install.install(
            source_dir=source_dir,
            dispatcher_path=dispatcher_path,
            config_files=(("cflan_vars.yaml", "/should-not-be-used"),),
        )

        output = capsys.readouterr().out
        assert "Warning: No configuration file found." in output
        assert privileged_calls.chmod.call_count == 1
