from __future__ import annotations

from pathlib import Path

import pytest

import run as launcher


def profile_environment() -> dict[str, str]:
    return {
        "NARA_HERMES_MODEL": "@cf/example/model",
        "NARA_SEARCH_URL": "http://127.0.0.1:8100",
        "NARA_COMBINER_URL": "http://127.0.0.1:8103",
        "NARA_COMPOSE_TIMEOUT": "123",
        "NARA_STORAGE_DIR": r"C:\project\test-storage",
        "NARA_INDEX_BUILT_AT": "2026-08-13T00:00:00Z",
        "CLOUDFLARE_ACCOUNT_ID": "account-secret",
        "CLOUDFLARE_API_TOKEN": "token-secret",
        "NARA_CLOUDFLARE_PROXY_KEY": "proxy-secret",
    }


def test_rendered_profile_routes_only_to_loopback_proxy():
    rendered = launcher.render_hermes_profile(9876, profile_environment())

    assert 'base_url: "http://127.0.0.1:9876/v1"' in rendered
    assert 'provider: "custom:cloudflare_proxy"' in rendered
    assert "model_routes:" in rendered
    assert 'transport: "chat_completions"' in rendered
    assert "key_env: NARA_CLOUDFLARE_PROXY_KEY" in rendered
    assert "api.cloudflare.com" not in rendered
    assert "account-secret" not in rendered
    assert "token-secret" not in rendered
    assert "__NARA_" not in rendered


def test_runtime_profile_is_project_owned(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "hermes-runtime"
    monkeypatch.setattr(launcher, "HERMES_RUNTIME_ROOT", runtime_root)

    config_path = launcher.ensure_hermes_runtime_profile(
        "nara-cf", 9876, profile_environment()
    )

    assert config_path == runtime_root / "profiles" / "nara-cf" / "config.yaml"
    assert config_path.is_file()
    assert "http://127.0.0.1:9876/v1" in config_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("profile", ["../escape", "..", "bad/name", "bad name"])
def test_runtime_profile_rejects_unsafe_names(profile: str):
    with pytest.raises(RuntimeError, match="안전하지 않은"):
        launcher.ensure_hermes_runtime_profile(profile, 9876, profile_environment())


def test_proxy_configuration_reports_missing_names():
    with pytest.raises(RuntimeError) as error:
        launcher.validate_proxy_configuration(
            {
                "CLOUDFLARE_ACCOUNT_ID": "",
                "CLOUDFLARE_API_TOKEN": "token",
                "NARA_CLOUDFLARE_PROXY_KEY": "",
            }
        )

    message = str(error.value)
    assert "CLOUDFLARE_ACCOUNT_ID" in message
    assert "NARA_CLOUDFLARE_PROXY_KEY" in message
    assert "CLOUDFLARE_API_TOKEN" not in message


def test_start_hermes_pins_profile_home_and_uses_python_process(monkeypatch):
    captured: dict[str, object] = {}
    environment = profile_environment()
    environment["NARA_HERMES_PROFILE"] = "nara-cf"
    executable = launcher.hermes_executable()
    config_path = (
        launcher.HERMES_RUNTIME_ROOT / "profiles" / "nara-cf" / "config.yaml"
    )

    class DummyProcess:
        pid = 1234

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr(launcher, "child_environment", lambda: environment.copy())
    monkeypatch.setattr(launcher, "validate_proxy_configuration", lambda _: None)
    monkeypatch.setattr(
        launcher,
        "ensure_hermes_runtime_profile",
        lambda *_: config_path,
    )
    monkeypatch.setattr(launcher, "hermes_executable", lambda: executable)
    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    launcher.start_hermes("nara-cf", 9876)

    command = captured["command"]
    kwargs = captured["kwargs"]
    expected_environment: dict[str, str] = {}
    expected_python = launcher.hermes_python_executable(
        executable, expected_environment
    )
    assert command[:3] == [
        str(expected_python),
        "-m",
        "hermes_cli.main",
    ]
    assert "-p" not in command
    assert kwargs["env"]["HERMES_HOME"] == str(config_path.parent)
    assert kwargs["env"]["HERMES_PROFILE"] == "nara-cf"
    assert kwargs["env"]["HERMES_INFERENCE_PROVIDER"] == "custom:cloudflare_proxy"
    if "__PYVENV_LAUNCHER__" in expected_environment:
        assert (
            kwargs["env"]["__PYVENV_LAUNCHER__"]
            == expected_environment["__PYVENV_LAUNCHER__"]
        )


def test_start_hermes_drops_inherited_environment_paths(monkeypatch):
    """Hermes runs on another Python version; our venv must not reach it."""
    captured: dict[str, object] = {}
    environment = profile_environment()
    environment["NARA_HERMES_PROFILE"] = "nara-cf"
    environment["PYTHONPATH"] = str(launcher.BASE_DIR / "venv" / "Lib" / "site-packages")
    environment["PYTHONHOME"] = str(launcher.BASE_DIR / "venv")
    environment["VIRTUAL_ENV"] = str(launcher.BASE_DIR / "venv")
    executable = launcher.hermes_executable()
    config_path = (
        launcher.HERMES_RUNTIME_ROOT / "profiles" / "nara-cf" / "config.yaml"
    )

    class DummyProcess:
        pid = 1234

    def fake_popen(command, **kwargs):
        captured["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr(launcher, "child_environment", lambda: environment.copy())
    monkeypatch.setattr(launcher, "validate_proxy_configuration", lambda _: None)
    monkeypatch.setattr(launcher, "ensure_hermes_runtime_profile", lambda *_: config_path)
    monkeypatch.setattr(launcher, "hermes_executable", lambda: executable)
    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    launcher.start_hermes("nara-cf", 9876)

    child_env = captured["kwargs"]["env"]
    assert "PYTHONPATH" not in child_env
    assert "PYTHONHOME" not in child_env
    assert "VIRTUAL_ENV" not in child_env


def test_gateway_state_must_match_project_process(monkeypatch, tmp_path: Path):
    runtime_root = tmp_path / "hermes-runtime"
    state_dir = runtime_root / "profiles" / "nara-cf"
    state_dir.mkdir(parents=True)
    (state_dir / "gateway_state.json").write_text(
        '{"pid":1234,"kind":"hermes-gateway","gateway_state":"running"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "HERMES_RUNTIME_ROOT", runtime_root)

    assert launcher.gateway_state_matches("nara-cf", 1234)
    assert not launcher.gateway_state_matches("nara-cf", 9999)
