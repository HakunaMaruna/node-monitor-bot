import argparse
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SHELL_METACHARS = frozenset(";|&$`><()\n")
DEFAULT_FETCH_COMMAND = ("git", "fetch", "--tags", "origin")
DEFAULT_UPDATE_COMMANDS = (
    ("docker", "compose", "pull"),
    ("docker", "compose", "up", "-d", "--force-recreate", "--remove-orphans"),
)
DEFAULT_STOP_COMMANDS = (("docker", "compose", "down"),)
DEFAULT_ROLLBACK_START_COMMANDS = (
    ("docker", "compose", "build"),
    ("docker", "compose", "up", "-d", "--force-recreate", "--remove-orphans"),
)


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def split_command_line(value: str) -> tuple[str, ...]:
    """Разбирает строку команды в argv, не отдавая её shell."""
    argv = tuple(shlex.split(value))
    for arg in argv:
        if any(char in arg for char in SHELL_METACHARS):
            raise RuntimeError(
                f"Команда '{value}' содержит символы оболочки. "
                "Опишите её отдельными аргументами без |, ;, &, $ и перенаправлений."
            )
    return argv


def parse_command_chain(value: str | None, default: tuple[tuple[str, ...], ...]):
    if value is None or not value.strip():
        return default
    commands = []
    for part in value.split("&&"):
        argv = split_command_line(part)
        if not argv:
            raise RuntimeError(f"Пустая команда в '{value}'")
        commands.append(argv)
    return tuple(commands)


def parse_single_command(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return default
    argv = split_command_line(value)
    if not argv:
        raise RuntimeError(f"Пустая команда в '{value}'")
    return argv


@dataclass
class UpdaterConfig:
    deploy_dir: Path
    bot_token: str
    chat_id: str
    github_repo: str
    github_token: str
    backup_dir: Path
    include_env: bool
    check_interval_sec: int
    fetch_command: tuple[str, ...]
    update_commands: tuple[tuple[str, ...], ...]
    stop_commands: tuple[tuple[str, ...], ...]
    rollback_start_commands: tuple[tuple[str, ...], ...]
    telegram_api: str
    send_backup: bool = False
    require_signed_tags: bool = False

    @classmethod
    def from_env(cls, deploy_dir: str | None = None) -> "UpdaterConfig":
        root = Path(deploy_dir or os.getenv("DEPLOY_DIR") or Path.cwd()).resolve()
        load_env_file(root / ".env")
        backup_dir = Path(os.getenv("BACKUP_DIR") or root / "backups")
        if not backup_dir.is_absolute():
            backup_dir = root / backup_dir
        backup_dir = backup_dir.resolve()
        return cls(
            deploy_dir=root,
            bot_token=os.getenv("BOT_TOKEN", ""),
            chat_id=os.getenv("ALERT_CHAT_ID") or os.getenv("ADMIN_ID") or "",
            github_repo=os.getenv("GITHUB_REPO", "HakunaMaruna/node-monitor-bot"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            backup_dir=backup_dir,
            include_env=os.getenv("INCLUDE_ENV", "0") not in {"0", "false", "False"},
            send_backup=os.getenv("SEND_BACKUP", "0") not in {"0", "false", "False"},
            require_signed_tags=os.getenv("REQUIRE_SIGNED_TAGS", "0") not in {"0", "false", "False"},
            check_interval_sec=int(os.getenv("CHECK_INTERVAL_SEC", "3600")),
            fetch_command=parse_single_command(os.getenv("FETCH_COMMAND"), DEFAULT_FETCH_COMMAND),
            update_commands=parse_command_chain(os.getenv("UPDATE_COMMAND"), DEFAULT_UPDATE_COMMANDS),
            stop_commands=parse_command_chain(os.getenv("STOP_COMMAND"), DEFAULT_STOP_COMMANDS),
            rollback_start_commands=parse_command_chain(
                os.getenv("ROLLBACK_START_COMMAND"), DEFAULT_ROLLBACK_START_COMMANDS
            ),
            telegram_api=os.getenv("TELEGRAM_API", "https://api.telegram.org").rstrip("/"),
        )


def local_version(deploy_dir: Path) -> str:
    version_file = deploy_dir / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0"


def ensure_clean_worktree(config: UpdaterConfig) -> None:
    status = run_command(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        config.deploy_dir,
    )
    if status:
        raise RuntimeError(
            "В каталоге обновления есть незакоммиченные изменения. "
            "Обновление остановлено, чтобы не потерять правки:\n"
            f"{status[:2000]}"
        )


def verify_origin(config: UpdaterConfig) -> None:
    url = run_command(("git", "remote", "get-url", "origin"), config.deploy_dir).strip()
    normalized = url.lower().rstrip("/").replace(":", "/")
    if normalized.endswith(".git"):
        normalized = normalized[: -len(".git")]
    expected = f"github.com/{config.github_repo}".lower().rstrip("/")
    if expected not in normalized:
        raise RuntimeError(
            f"origin указывает не на {config.github_repo}: {url}. Обновление остановлено."
        )


def verify_tag_signature(config: UpdaterConfig, tag: str) -> None:
    allowed_signers = config.deploy_dir / ".allowed_signers"
    if allowed_signers.is_file():
        run_command(
            (
                "git",
                "-c",
                f"gpg.ssh.allowedSignersFile={allowed_signers}",
                "verify-tag",
                "--raw",
                tag,
            ),
            config.deploy_dir,
        )
        return
    if config.require_signed_tags:
        raise RuntimeError(
            "Тег не проверен: нет файла .allowed_signers в каталоге деплоя, "
            "а REQUIRE_SIGNED_TAGS=1. Обновление остановлено."
        )
    print(
        "ВНИМАНИЕ: .allowed_signers не найден, подпись тега не проверяется. "
        "Добавьте .allowed_signers и REQUIRE_SIGNED_TAGS=1.",
        flush=True,
    )


def parse_version(value: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in re.findall(r"\d+", value))
    return parts + (0,) * (3 - len(parts)) if len(parts) < 3 else parts


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def github_request(config: UpdaterConfig, path: str) -> dict | None:
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "node-monitor-updater",
    }
    if config.github_token:
        headers["Authorization"] = f"Bearer {config.github_token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"GitHub API вернул HTTP {exc.code}") from exc


def latest_release(config: UpdaterConfig) -> dict | None:
    return github_request(config, f"/repos/{config.github_repo}/releases/latest")


def telegram_request(
    config: UpdaterConfig,
    method: str,
    data: dict,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> dict:
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не задан")
    if not config.chat_id:
        raise RuntimeError("ADMIN_ID или ALERT_CHAT_ID не задан")
    url = f"{config.telegram_api}/bot{config.bot_token}/{method}"

    if files is None:
        body = json.dumps({**data, "chat_id": config.chat_id}).encode()
        headers = {"Content-Type": "application/json"}
    else:
        boundary = f"----NodeMonitorUpdater{uuid.uuid4().hex}"
        chunks = []
        for key, value in {**data, "chat_id": config.chat_id}.items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            chunks.append(f"{value}\r\n".encode())
        for field, (filename, content, content_type) in files.items():
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
            )
            chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
            chunks.append(content)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram отклонил {method}")
    return result


def send_message(config: UpdaterConfig, text: str) -> None:
    telegram_request(config, "sendMessage", {"text": text})


def send_backup(config: UpdaterConfig, backup_path: Path, version: str) -> None:
    size = backup_path.stat().st_size
    if size > 45 * 1024 * 1024:
        raise RuntimeError("Архив бэкапа больше 45 МБ, Telegram не примет его как документ")
    caption = f"Бэкап Node Monitor Bot перед обновлением до {version}"
    if config.include_env:
        caption += " (с .env — удалите сообщение после восстановления)"
    telegram_request(
        config,
        "sendDocument",
        {"caption": caption},
        {"document": (backup_path.name, backup_path.read_bytes(), "application/gzip")},
    )


def create_backup(config: UpdaterConfig, version: str) -> Path:
    config.backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(config.backup_dir, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = config.backup_dir / f"node-monitor-backup-{version}-{stamp}.tar.gz"
    excluded_dirs = {
        ".git",
        "backups",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".trail",
        "venv",
        ".venv",
    }
    excluded_suffixes = {".pyc", ".pyo"}

    files = []
    for path in sorted(config.deploy_dir.rglob("*")):
        relative = path.relative_to(config.deploy_dir)
        if any(part in excluded_dirs for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix in excluded_suffixes:
            continue
        if not config.include_env and relative == Path(".env"):
            continue
        if path.name.startswith("node-monitor-backup-") and path.name.endswith(".tar.gz"):
            continue
        files.append((path, relative.as_posix()))

    manifest = json.dumps(
        {
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "include_env": config.include_env,
            "files": [name for _, name in files],
        },
        ensure_ascii=False,
        indent=2,
    ).encode()

    with tarfile.open(backup_path, "w:gz") as archive:
        for path, name in files:
            archive.add(path, arcname=name, recursive=False)
        info = tarfile.TarInfo(".updater/manifest.json")
        info.size = len(manifest)
        info.mtime = int(time.time())
        archive.addfile(info, io.BytesIO(manifest))
    os.chmod(backup_path, 0o600)
    return backup_path


def safe_extract(backup_path: Path, target: Path) -> None:
    root = target.resolve()
    with tarfile.open(backup_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name.startswith(".updater/"):
                continue
            destination = (root / member.name).resolve()
            if destination != root and root not in destination.parents:
                raise RuntimeError(f"Небезопасный путь в архиве: {member.name}")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Не удалось прочитать {member.name} из архива")
                with destination.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)


def run_command(argv: tuple[str, ...] | list[str], cwd: Path) -> str:
    if not argv:
        return ""
    result = subprocess.run(
        list(argv),
        shell=False,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()[-2000:]
        raise RuntimeError(
            f"Команда '{' '.join(argv)}' завершилась с кодом {result.returncode}:\n{output}"
        )
    return (result.stdout + result.stderr).strip()


def rollback(config: UpdaterConfig, backup_path: Path) -> None:
    if not backup_path.exists():
        raise RuntimeError(f"Файл бэкапа не найден: {backup_path}")
    for command in config.stop_commands:
        run_command(command, config.deploy_dir)
    safe_extract(backup_path, config.deploy_dir)
    for command in config.rollback_start_commands:
        run_command(command, config.deploy_dir)


def prepare_update(config: UpdaterConfig, version: str) -> str:
    """Проверяет источник обновления и возвращает имя тега. Ничего не меняет на диске."""
    tag = version if version.startswith("v") else f"v{version}"
    ensure_clean_worktree(config)
    verify_origin(config)
    run_command(config.fetch_command, config.deploy_dir)
    run_command(("git", "rev-parse", "--verify", f"refs/tags/{tag}"), config.deploy_dir)
    verify_tag_signature(config, tag)
    return tag


def perform_update(config: UpdaterConfig, version: str, *, tag: str | None = None) -> None:
    tag = tag or prepare_update(config, version)
    run_command(("git", "checkout", "--detach", tag), config.deploy_dir)
    checked = local_version(config.deploy_dir)
    if parse_version(checked) != parse_version(tag):
        raise RuntimeError(
            f"После checkout {tag} в VERSION указана версия {checked}. "
            "Обновление остановлено, чтобы не запустить чужой код."
        )
    for command in config.update_commands:
        run_command(command, config.deploy_dir)


def update_flow(config: UpdaterConfig) -> bool:
    local = local_version(config.deploy_dir)
    release = latest_release(config)
    if release is None:
        return False
    version = release.get("tag_name", "").strip()
    if not version or not is_newer(version, local):
        return False

    try:
        tag = prepare_update(config, version)
    except RuntimeError as exc:
        send_message(config, f"Автообновление до {version} не запущено.\n{exc}")
        return False

    backup_path = create_backup(config, version)
    if config.send_backup:
        send_backup(config, backup_path, version)
    url = release.get("html_url", "")
    backup_note = (
        f"Бэкап отправлен: {backup_path.name}"
        if config.send_backup
        else f"Бэкап сохранён локально: {backup_path.name}"
    )
    send_message(
        config,
        f"Доступна версия {version} Node Monitor Bot.\n"
        f"{backup_note}\n"
        f"Начинаю автообновление.\n{url}",
    )

    try:
        perform_update(config, version, tag=tag)
    except Exception as exc:
        try:
            rollback(config, backup_path)
            recovery = "Откат из бэкапа выполнен."
        except Exception as rollback_error:
            recovery = f"Откат не удался: {rollback_error}"
        send_message(
            config,
            f"Обновление до {version} не удалось: {exc}\n{recovery}\nБэкап: {backup_path.name}",
        )
        raise

    send_message(config, f"Node Monitor Bot обновлён до версии {version}.")
    return True


def daemon(config: UpdaterConfig) -> None:
    while True:
        try:
            update_flow(config)
        except Exception as exc:
            print(f"Updater error: {exc}", flush=True)
        time.sleep(config.check_interval_sec)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Updater for Node Monitor Bot")
    parser.add_argument("--deploy-dir", help="Каталог развёрнутого бота")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Показать локальную и последнюю версию")
    backup_parser = subparsers.add_parser("backup", help="Создать и отправить бэкап")
    backup_parser.add_argument("--no-send", action="store_true")
    backup_parser.add_argument("--no-env", action="store_true")
    subparsers.add_parser("update", help="Проверить и применить обновление")
    rollback_parser = subparsers.add_parser("rollback", help="Откатиться из бэкапа")
    rollback_parser.add_argument("backup_path")
    subparsers.add_parser("daemon", help="Периодическая проверка обновлений")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = UpdaterConfig.from_env(args.deploy_dir)
    if getattr(args, "no_env", False):
        config.include_env = False

    if args.command == "check":
        local = local_version(config.deploy_dir)
        release = latest_release(config)
        remote = release.get("tag_name", "-") if release else "-"
        print(f"local: {local}\nremote: {remote}\nnewer: {is_newer(remote, local) if release else False}")
        return 0

    if args.command == "backup":
        version = local_version(config.deploy_dir)
        path = create_backup(config, version)
        if not args.no_send:
            send_backup(config, path, version)
        print(path)
        return 0

    if args.command == "update":
        print("updated" if update_flow(config) else "no update")
        return 0

    if args.command == "rollback":
        rollback(config, Path(args.backup_path).resolve())
        send_message(config, f"Откат Node Monitor Bot выполнен из {Path(args.backup_path).name}")
        return 0

    daemon(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
