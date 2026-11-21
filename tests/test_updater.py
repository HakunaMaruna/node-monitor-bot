import json
import stat
import tarfile
from types import SimpleNamespace

import pytest

import updater
from updater import UpdaterConfig


def make_config(tmp_path, *, include_env=False, send_backup=False) -> UpdaterConfig:
    return UpdaterConfig(
        deploy_dir=tmp_path / "deploy",
        bot_token="token",
        chat_id="42",
        github_repo="HakunaMaruna/node-monitor-bot",
        github_token="",
        backup_dir=tmp_path / "backups",
        include_env=include_env,
        check_interval_sec=1,
        fetch_command=("git", "fetch", "--tags", "origin"),
        update_commands=(("docker", "compose", "up", "-d"),),
        stop_commands=(("docker", "compose", "down"),),
        rollback_start_commands=(("docker", "compose", "up", "-d"),),
        telegram_api="https://api.telegram.org",
        send_backup=send_backup,
        require_signed_tags=False,
    )


def seed_deploy(config) -> None:
    config.deploy_dir.mkdir(parents=True)
    (config.deploy_dir / "VERSION").write_text("1.0\n", encoding="utf-8")
    (config.deploy_dir / ".env").write_text("BOT_TOKEN=secret\n", encoding="utf-8")
    (config.deploy_dir / "nodes.db").write_bytes(b"database")
    (config.deploy_dir / "app").mkdir()
    (config.deploy_dir / "app" / "main.py").write_text("print(1)", encoding="utf-8")
    (config.deploy_dir / "__pycache__").mkdir()
    (config.deploy_dir / "__pycache__" / "main.pyc").write_bytes(b"cache")


def test_version_comparison():
    assert updater.parse_version("v1.0") == (1, 0, 0)
    assert updater.parse_version("1.2.3") == (1, 2, 3)
    assert updater.is_newer("v1.1", "1.0") is True
    assert updater.is_newer("v1.0", "1.0") is False
    assert updater.is_newer("0.9", "1.0") is False


def test_from_env_loads_dotenv_without_overriding_environment(tmp_path, monkeypatch):
    root = tmp_path / "deploy"
    root.mkdir()
    (root / ".env").write_text(
        'BOT_TOKEN=from-file\n'
        'ADMIN_ID=99\n'
        'BACKUP_DIR=backups\n'
        'INCLUDE_ENV=1\n'
        'UPDATE_COMMAND=docker compose pull && docker compose up -d\n',
        encoding="utf-8",
    )
    for key in (
        "DEPLOY_DIR",
        "BACKUP_DIR",
        "BOT_TOKEN",
        "ADMIN_ID",
        "ALERT_CHAT_ID",
        "INCLUDE_ENV",
        "SEND_BACKUP",
        "REQUIRE_SIGNED_TAGS",
        "UPDATE_COMMAND",
        "FETCH_COMMAND",
        "STOP_COMMAND",
        "ROLLBACK_START_COMMAND",
        "GITHUB_REPO",
    ):
        monkeypatch.delenv(key, raising=False)

    config = UpdaterConfig.from_env(str(root))
    assert config.bot_token == "from-file"
    assert config.chat_id == "99"
    assert config.backup_dir == root / "backups"
    assert config.include_env is True
    assert config.send_backup is False
    assert config.update_commands == (
        ("docker", "compose", "pull"),
        ("docker", "compose", "up", "-d"),
    )

    monkeypatch.setenv("BOT_TOKEN", "from-env")
    assert UpdaterConfig.from_env(str(root)).bot_token == "from-env"


def test_include_env_and_backup_sending_are_off_by_default(tmp_path, monkeypatch):
    root = tmp_path / "deploy"
    root.mkdir()
    for key in ("INCLUDE_ENV", "SEND_BACKUP", "REQUIRE_SIGNED_TAGS", "BOT_TOKEN", "ADMIN_ID", "DEPLOY_DIR"):
        monkeypatch.delenv(key, raising=False)
    (root / ".env").write_text("BOT_TOKEN=token\nADMIN_ID=1\n", encoding="utf-8")

    config = UpdaterConfig.from_env(str(root))

    assert config.include_env is False
    assert config.send_backup is False
    assert config.require_signed_tags is False


def test_command_with_shell_metachars_is_rejected():
    with pytest.raises(RuntimeError, match="символы оболочки"):
        updater.parse_command_chain("docker compose up; rm -rf /", updater.DEFAULT_UPDATE_COMMANDS)
    with pytest.raises(RuntimeError, match="символы оболочки"):
        updater.parse_single_command("git fetch $(whoami)", updater.DEFAULT_FETCH_COMMAND)


def test_run_command_does_not_use_shell(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)

    assert updater.run_command(("git", "status"), tmp_path) == "ok"
    assert calls[0][0] == ["git", "status"]
    assert calls[0][1]["shell"] is False


def test_verify_origin_rejects_foreign_remote(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    monkeypatch.setattr(
        updater,
        "run_command",
        lambda argv, cwd: "https://github.com/evil/mirror.git",
    )

    with pytest.raises(RuntimeError, match="origin указывает не на"):
        updater.verify_origin(config)


def test_verify_origin_accepts_expected_remote(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    for remote in (
        "https://github.com/HakunaMaruna/node-monitor-bot.git",
        "git@github.com:HakunaMaruna/node-monitor-bot.git",
    ):
        monkeypatch.setattr(updater, "run_command", lambda argv, cwd, remote=remote: remote)
        updater.verify_origin(config)


def test_verify_tag_signature_requires_allowed_signers_when_enabled(tmp_path):
    config = make_config(tmp_path)
    seed_deploy(config)
    config.require_signed_tags = True

    with pytest.raises(RuntimeError, match=".allowed_signers"):
        updater.verify_tag_signature(config, "v1.1")


def test_verify_tag_signature_uses_git(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    (config.deploy_dir / ".allowed_signers").write_text("key\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(updater, "run_command", lambda argv, cwd: calls.append(argv) or "")

    updater.verify_tag_signature(config, "v1.1")

    assert calls[0][0] == "git"
    assert "verify-tag" in calls[0]


def test_create_backup_contains_code_and_env(tmp_path):
    config = make_config(tmp_path, include_env=True)
    seed_deploy(config)

    backup = updater.create_backup(config, "v1.1")

    assert backup.exists()
    with tarfile.open(backup, "r:gz") as archive:
        names = set(archive.getnames())
    assert "VERSION" in names
    assert ".env" in names
    assert "nodes.db" in names
    assert "app/main.py" in names
    assert ".updater/manifest.json" in names
    assert not any("__pycache__" in name for name in names)


def test_create_backup_can_exclude_env(tmp_path):
    config = make_config(tmp_path, include_env=False)
    seed_deploy(config)

    backup = updater.create_backup(config, "v1.1")

    with tarfile.open(backup, "r:gz") as archive:
        names = set(archive.getnames())
    assert ".env" not in names


def test_create_backup_restricts_permissions(tmp_path):
    config = make_config(tmp_path)
    seed_deploy(config)

    backup = updater.create_backup(config, "v1.1")

    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(config.backup_dir.stat().st_mode) == 0o700


def test_safe_extract_restores_files(tmp_path):
    config = make_config(tmp_path)
    seed_deploy(config)
    backup = updater.create_backup(config, "v1.1")
    (config.deploy_dir / "nodes.db").write_bytes(b"broken")
    (config.deploy_dir / "app" / "main.py").write_text("broken", encoding="utf-8")

    updater.safe_extract(backup, config.deploy_dir)

    assert (config.deploy_dir / "nodes.db").read_bytes() == b"database"
    assert (config.deploy_dir / "app" / "main.py").read_text(encoding="utf-8") == "print(1)"
    assert not (config.deploy_dir / ".updater").exists()


def test_send_backup_uses_document_with_caption(tmp_path, monkeypatch):
    config = make_config(tmp_path, include_env=True)
    backup = tmp_path / "backup.tar.gz"
    backup.write_bytes(b"archive")
    calls = []

    def fake_request(config_arg, method, data, files=None):
        calls.append((method, data, files))
        return {}

    monkeypatch.setattr(updater, "telegram_request", fake_request)
    updater.send_backup(config, backup, "v1.1")

    assert calls[0][0] == "sendDocument"
    assert "v1.1" in calls[0][1]["caption"]
    assert ".env" in calls[0][1]["caption"]
    assert calls[0][2]["document"][0] == "backup.tar.gz"
    assert calls[0][2]["document"][1] == b"archive"


def test_update_flow_sends_backup_before_notification_and_rolls_back(tmp_path, monkeypatch):
    config = make_config(tmp_path, send_backup=True)
    backup = tmp_path / "backup.tar.gz"
    backup.write_bytes(b"archive")
    events = []

    monkeypatch.setattr(
        updater,
        "latest_release",
        lambda config_arg: {"tag_name": "v1.1", "html_url": "https://example.test/release"},
    )
    monkeypatch.setattr(updater, "prepare_update", lambda config_arg, version: "v1.1")
    monkeypatch.setattr(updater, "create_backup", lambda config_arg, version: backup)
    monkeypatch.setattr(
        updater,
        "send_backup",
        lambda config_arg, path, version: events.append("backup"),
    )
    monkeypatch.setattr(
        updater,
        "send_message",
        lambda config_arg, text: events.append(text),
    )

    def failing_update(config_arg, version, *, tag=None):
        events.append("update")
        raise RuntimeError("update failed")

    def fake_rollback(config_arg, path):
        events.append("rollback")

    monkeypatch.setattr(updater, "perform_update", failing_update)
    monkeypatch.setattr(updater, "rollback", fake_rollback)

    with pytest.raises(RuntimeError, match="update failed"):
        updater.update_flow(config)

    assert events[0] == "backup"
    assert "Доступна версия v1.1" in events[1]
    assert events[2] == "update"
    assert events[3] == "rollback"
    assert "Откат из бэкапа выполнен" in events[4]


def test_update_flow_keeps_backup_local_by_default(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    backup = tmp_path / "backup.tar.gz"
    backup.write_bytes(b"archive")
    messages = []
    sent = []

    monkeypatch.setattr(
        updater,
        "latest_release",
        lambda config_arg: {"tag_name": "v1.1", "html_url": ""},
    )
    monkeypatch.setattr(updater, "prepare_update", lambda config_arg, version: "v1.1")
    monkeypatch.setattr(updater, "create_backup", lambda config_arg, version: backup)
    monkeypatch.setattr(updater, "send_backup", lambda *args: sent.append(args))
    monkeypatch.setattr(updater, "send_message", lambda config_arg, text: messages.append(text))
    monkeypatch.setattr(updater, "perform_update", lambda *args, **kwargs: None)

    assert updater.update_flow(config) is True
    assert sent == []
    assert "сохранён локально" in messages[0]


def test_update_flow_aborts_on_dirty_worktree(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    messages = []
    called = []

    monkeypatch.setattr(
        updater,
        "latest_release",
        lambda config_arg: {"tag_name": "v1.1", "html_url": ""},
    )
    monkeypatch.setattr(updater, "send_message", lambda config_arg, text: messages.append(text))

    def dirty(config_arg, version):
        raise RuntimeError("есть правки")

    monkeypatch.setattr(updater, "prepare_update", dirty)
    monkeypatch.setattr(
        updater, "create_backup", lambda config_arg, version: called.append("backup")
    )

    assert updater.update_flow(config) is False
    assert called == []
    assert "не запущено" in messages[0]
    assert "есть правки" in messages[0]


def test_update_flow_skips_current_version(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    called = []

    monkeypatch.setattr(
        updater,
        "latest_release",
        lambda config_arg: {"tag_name": "v1.0", "html_url": ""},
    )
    monkeypatch.setattr(
        updater, "create_backup", lambda config_arg, version: called.append("backup")
    )

    assert updater.update_flow(config) is False
    assert called == []


def test_perform_update_checks_clean_tree_and_version(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    commands = []

    def fake_run(argv, cwd):
        commands.append(argv)
        text = " ".join(argv)
        if text.startswith("git remote get-url"):
            return "git@github.com:HakunaMaruna/node-monitor-bot.git"
        if text.startswith("git checkout"):
            (config.deploy_dir / "VERSION").write_text("1.1\n", encoding="utf-8")
        return ""

    monkeypatch.setattr(updater, "run_command", fake_run)

    updater.perform_update(config, "v1.1")

    assert commands == [
        ("git", "status", "--porcelain", "--untracked-files=no"),
        ("git", "remote", "get-url", "origin"),
        ("git", "fetch", "--tags", "origin"),
        ("git", "rev-parse", "--verify", "refs/tags/v1.1"),
        ("git", "checkout", "--detach", "v1.1"),
        ("docker", "compose", "up", "-d"),
    ]


def test_perform_update_rejects_dirty_worktree(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    commands = []

    monkeypatch.setattr(
        updater,
        "run_command",
        lambda argv, cwd: commands.append(argv) or " M app/main.py",
    )

    with pytest.raises(RuntimeError, match="незакоммиченные изменения"):
        updater.perform_update(config, "v1.1")

    assert commands == [("git", "status", "--porcelain", "--untracked-files=no")]


def test_perform_update_rejects_version_mismatch(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    seed_deploy(config)
    commands = []

    def fake_run(argv, cwd):
        commands.append(argv)
        if argv[:3] == ("git", "remote", "get-url"):
            return "https://github.com/HakunaMaruna/node-monitor-bot"
        return ""

    monkeypatch.setattr(updater, "run_command", fake_run)

    with pytest.raises(RuntimeError, match="VERSION указана версия 1.0"):
        updater.perform_update(config, "v1.1")

    assert ("docker", "compose", "up", "-d") not in commands


def test_rollback_restores_and_restarts(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    backup = tmp_path / "backup.tar.gz"
    backup.write_bytes(b"archive")
    commands = []

    monkeypatch.setattr(
        updater, "run_command", lambda argv, cwd: commands.append(argv) or ""
    )
    monkeypatch.setattr(updater, "safe_extract", lambda path, target: commands.append("extract"))

    updater.rollback(config, backup)

    assert commands == [("docker", "compose", "down"), "extract", ("docker", "compose", "up", "-d")]


def test_latest_release_parses_github_json(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    payload = {"tag_name": "v1.1", "html_url": "https://example.test/release"}

    def fake_urlopen(request, timeout):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode()

        return Response()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    assert updater.latest_release(config) == payload
