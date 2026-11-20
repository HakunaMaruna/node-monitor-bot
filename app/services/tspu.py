import asyncio
import socket
import ssl
from urllib.parse import quote

import aiohttp

from app.utils.design import esc


BLOCKED_TEST_IP = "173.194.222.113"
SNI_TEST_IP = "77.88.55.242"
DNS_SERVERS = ("8.8.8.8", "1.1.1.1", "77.88.8.8")
CHECKED_SITES = ("ya.ru", "google.com", "youtube.com", "github.com", "telegram.org")
COMMON_PORTS = (22, 80, 443, 8080, 8443)
DETAILED_PORTS = (22, 80, 443, 3306, 5432, 8080, 8443)


async def _run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


def _local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "не определён"


async def _ping(host: str, count: int = 2, timeout: int = 5) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", str(count), "-W", "2", host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        return proc.returncode == 0
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        return False


async def _tcp_open(host: str, port: int, timeout: int = 4) -> tuple[bool, str]:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, "открыт"
    except asyncio.TimeoutError:
        return False, "таймаут"
    except ConnectionRefusedError:
        return False, "отклонено"
    except OSError as exc:
        return False, str(exc) or "нет ответа"


async def _http_status(url: str, timeout: int = 8) -> str:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, allow_redirects=True) as response:
                return str(response.status)
    except asyncio.TimeoutError:
        return "таймаут"
    except Exception as exc:
        return f"ошибка: {exc}"


async def _fetch_text(url: str, timeout: int = 8) -> str:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, allow_redirects=True) as response:
                return (await response.text()).strip()
    except Exception:
        return ""


async def _peer_ip(url: str, timeout: int = 8) -> str:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, allow_redirects=True) as response:
                connection = getattr(response, "connection", None)
                transport = getattr(connection, "transport", None) if connection else None
                peer = transport.get_extra_info("peername") if transport else None
                if peer:
                    return str(peer[0])
                return ""
    except Exception:
        return ""


async def _doh_resolve(domain: str, timeout: int = 6) -> str:
    url = f"https://1.1.1.1/dns-query?name={quote(domain)}&type=A"
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url, headers={"accept": "application/dns-json"}) as response:
                data = await response.json(content_type=None)
                answers = data.get("Answer") or []
                for answer in answers:
                    if answer.get("type") == 1:
                        return str(answer.get("data", ""))
                return ""
    except Exception:
        return ""


def _encode_dns_name(name: str) -> bytes:
    result = b""
    for part in name.strip(".").split("."):
        raw = part.encode("ascii")
        result += bytes((len(raw),)) + raw
    return result + b"\x00"


def _decode_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    labels = []
    jumped = False
    original_offset = offset
    visited = set()
    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                original_offset = offset + 2
                jumped = True
            offset = pointer
            if pointer in visited:
                break
            visited.add(pointer)
            continue
        offset += 1
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    name = ".".join(labels)
    return name, (original_offset if jumped else offset)


def _sync_udp_dns_resolve(server: str, domain: str, timeout: int = 3) -> str:
    query = b""
    query += b"\x12\x34"
    query += b"\x01\x00"
    query += b"\x00\x01"
    query += b"\x00\x00\x00\x00\x00\x00"
    query += _encode_dns_name(domain)
    query += b"\x00\x01"
    query += b"\x00\x01"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(query, (server, 53))
        data, _ = sock.recvfrom(512)
    except OSError:
        return ""
    finally:
        sock.close()

    if len(data) < 12:
        return ""
    qdcount = int.from_bytes(data[4:6], "big")
    ancount = int.from_bytes(data[6:8], "big")
    offset = 12
    for _ in range(qdcount):
        _, offset = _decode_dns_name(data, offset)
        offset += 4
    for _ in range(ancount):
        _, offset = _decode_dns_name(data, offset)
        if offset + 10 > len(data):
            return ""
        rtype = int.from_bytes(data[offset:offset + 2], "big")
        offset += 8
        rdlength = int.from_bytes(data[offset:offset + 2], "big")
        offset += 2
        if rtype == 1 and rdlength == 4:
            return ".".join(str(byte) for byte in data[offset:offset + 4])
        offset += rdlength
    return ""


async def _udp_dns_resolve(server: str, domain: str, timeout: int = 3) -> str:
    return await _run_in_executor(_sync_udp_dns_resolve, server, domain, timeout)


async def _sni_check(ip: str, sni: str, timeout: int = 6) -> tuple[bool, str]:
    def sync() -> tuple[bool, str]:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((ip, 443), timeout=timeout) as raw:
                with context.wrap_socket(raw, server_hostname=sni) as wrapped:
                    return True, wrapped.version() or "TLS"
        except ConnectionResetError:
            return False, "RST"
        except ssl.SSLError as exc:
            return False, f"TLS ошибка: {exc}"
        except (socket.timeout, TimeoutError):
            return False, "таймаут"
        except OSError as exc:
            return False, str(exc) or "нет ответа"

    return await _run_in_executor(sync)


async def _cgnat_status(external_ip: str) -> bool:
    try:
        parts = external_ip.split(".")
        if len(parts) != 4:
            return False
        first, second = int(parts[0]), int(parts[1])
        return first == 100 and 64 <= second <= 127
    except (ValueError, IndexError):
        return False


def _ok(value: bool) -> str:
    return "✅" if value else "❌"


def _line(label: str, value: str) -> str:
    return f"  <b>{esc(label)}:</b> {value}"


async def run_tspu_quick(node) -> str:
    target = node.ip
    lines = [
        "🛡️ <b>ДИАГНОСТИКА ТСПУ</b>",
        f"Нода <b>#{node.id}</b> · {esc(target)}",
        "━" * 28,
    ]

    # 1. Режим ТСПУ
    icmp_ok = await _ping(BLOCKED_TEST_IP)
    tcp_ok, tcp_reason = await _tcp_open(BLOCKED_TEST_IP, 443)
    lines.extend(
        [
            "",
            "🧪 <b>Режим ТСПУ</b> <i>(173.194.222.113)</i>",
            f"  {_ok(icmp_ok)} ICMP: {'доступен' if icmp_ok else 'недоступен'}",
            f"  {_ok(tcp_ok)} TCP 443: {esc(tcp_reason)}",
        ]
    )
    if icmp_ok and not tcp_ok:
        lines.append("  ➜ похоже на <b>белые списки (allowlist)</b>")
    elif not icmp_ok and not tcp_ok:
        lines.append("  ➜ похоже на <b>чёрные списки / полную блокировку</b>")
    elif icmp_ok and tcp_ok:
        lines.append("  ➜ <b>блокировок не обнаружено</b>")

    # 2. Доступность целевого сервера
    lines.extend(["", f"🖥️ <b>Сервер {esc(target)}</b>"])
    for port in (22, 80, 443, 8080, 8443):
        ok, reason = await _tcp_open(target, port)
        lines.append(f"  {_ok(ok)} Порт {port}: {esc(reason)}")
    scheme = "https" if str(node.protocol).upper() == "HTTPS" else "http"
    status = await _http_status(f"{scheme}://{target}:{node.port}")
    lines.append(
        f"  {_ok(status.isdigit() and int(status) < 400)} HTTP {scheme}://{esc(target)}:{node.port}: {esc(status)}"
    )

    # 3. SNI-фильтрация
    lines.extend(["", f"🎭 <b>SNI-фильтрация</b> <i>({SNI_TEST_IP})</i>"])
    for sni, name in (
        ("ya.ru", "Яндекс"),
        ("google.com", "Google"),
        ("twitter.com", "Twitter"),
        ("youtube.com", "YouTube"),
        ("vk.com", "VK"),
    ):
        ok, reason = await _sni_check(SNI_TEST_IP, sni)
        lines.append(f"  {_ok(ok)} {esc(name)} ({esc(sni)}): {'пропущен' if ok else esc(reason)}")

    # 4. Внешние DNS
    lines.extend(["", "🌐 <b>Внешние DNS</b> <i>(ya.ru)</i>"])
    for server in DNS_SERVERS:
        ip = await _udp_dns_resolve(server, "ya.ru")
        lines.append(f"  {_ok(bool(ip))} {esc(server)} → {esc(ip) if ip else 'нет ответа'}")

    # 5. Расширенная диагностика блокировок
    lines.extend(["", "🔬 <b>Блокировки</b> <i>(ya.ru / twitter.com)</i>"])
    for domain in ("ya.ru", "twitter.com"):
        try:
            sys_ip = await _run_in_executor(lambda d: socket.gethostbyname(d), domain)
        except OSError:
            sys_ip = ""
        doh_ip = await _doh_resolve(domain)
        tcp_domain_ok, _ = await _tcp_open(domain, 443)
        tls_result = ""
        if tcp_domain_ok:
            ok, reason = await _sni_check(domain, domain)
            tls_result = "TLS ok" if ok else reason
        lines.extend(
            [
                f"  <b>{esc(domain)}</b>",
                f"    DNS системный: {esc(sys_ip) if sys_ip else 'нет ответа'}",
                f"    DNS DoH: {esc(doh_ip) if doh_ip else 'нет ответа'}",
                f"    TCP 443: {'открыт' if tcp_domain_ok else 'закрыт/фильтр'}",
            ]
        )
        if tcp_domain_ok:
            lines.append(f"    TLS: {esc(tls_result)}")

    # 6. NAT
    external_ip = await _fetch_text("https://api.ipify.org")
    if not external_ip:
        external_ip = await _fetch_text("https://ifconfig.me/ip")
    cgnat = await _cgnat_status(external_ip) if external_ip else False
    lines.extend(
        [
            "",
            "🌐 <b>NAT</b>",
            f"  Внешний IP: <code>{esc(external_ip) if external_ip else 'не определён'}</code>",
            f"  Локальный IP: <code>{esc(_local_ip())}</code>",
            f"  CGNAT: {'да' if cgnat else 'нет'}",
        ]
    )

    return "\n".join(lines)


async def run_tspu_full(node) -> str:
    base = await run_tspu_quick(node)
    target = node.ip
    lines = [base, "", "━" * 28, "🔬 <b>РАСШИРЕННАЯ ДИАГНОСТИКА</b>", "━" * 28]

    # Доступность сайтов
    lines.extend(["", "📡 <b>Доступность сайтов</b>"])
    for site in CHECKED_SITES:
        status = await _http_status(f"https://{site}")
        ok = status.isdigit() and int(status) < 400
        lines.append(f"  {_ok(ok)} {esc(site)}: HTTP {esc(status)}")

    # Детальный анализ портов
    service_names = {
        22: "SSH",
        80: "HTTP",
        443: "HTTPS",
        3306: "MySQL",
        5432: "PostgreSQL",
        8080: "HTTP-alt",
        8443: "HTTPS-alt",
    }
    lines.extend(["", f"📊 <b>Детальный анализ портов</b> <i>({esc(target)})</i>"])
    for port in DETAILED_PORTS:
        ok, reason = await _tcp_open(target, port)
        lines.append(
            f"  {_ok(ok)} {port:<5} {service_names.get(port, 'TCP'):<11} {esc(reason)}"
        )

    # UDP
    lines.extend(["", f"📦 <b>UDP</b> <i>({esc(target)})</i>"])
    dns_udp = await _udp_dns_resolve(target, "ya.ru", timeout=2)
    lines.append(
        f"  {_ok(bool(dns_udp))} UDP 53 (DNS): "
        + (f"отвечает → {esc(dns_udp)}" if dns_udp else "нет ответа (нормально, если не DNS-сервер)")
    )
    lines.append("  ℹ️ UDP 443/8443/51820: без ответа на пустые пакеты — это норма")

    # Split DNS
    lines.extend(["", "🔍 <b>Split DNS / утечка</b>"])
    ya_peer = await _peer_ip("https://ya.ru")
    ifconfig_ip = await _fetch_text("https://ifconfig.me/ip")
    lines.extend(
        [
            f"  ya.ru видит IP: <code>{esc(ya_peer) if ya_peer else 'не определён'}</code>",
            f"  ifconfig.me видит IP: <code>{esc(ifconfig_ip) if ifconfig_ip else 'не определён'}</code>",
        ]
    )
    if ya_peer and ifconfig_ip:
        if ya_peer != ifconfig_ip:
            lines.append("  ➜ split DNS/туннелирование работает")
        else:
            lines.append("  ➜ возможна утечка (оба видят один IP)")

    # My IP
    lines.extend(
        [
            "",
            "🌍 <b>Ваш IP</b>",
            f"  Внешний: <code>{esc(ifconfig_ip) if ifconfig_ip else 'не определён'}</code>",
            f"  Локальный: <code>{esc(_local_ip())}</code>",
        ]
    )

    return "\n".join(lines)