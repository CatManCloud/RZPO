import ipaddress
import logging
import socket
import tempfile
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


def _host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


def fetch_url(url: str) -> str:
    parsed = urlparse(url)
    # Только https и только публичные адреса (защита от SSRF)
    if parsed.scheme != "https" or not parsed.hostname or not _host_is_public(parsed.hostname):
        raise ValueError("URL is not allowed")
    # ИСПРАВЛЕНО (B501, B113): проверка сертификата включена, задан timeout
    r = requests.get(url, timeout=5, verify=True)
    r.raise_for_status()
    return r.text


def save_report(text: str) -> str:
    # ИСПРАВЛЕНО (B108): безопасный временный файл вместо фиксированного /tmp/report.txt
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text)
        return f.name


def safe_parse(value: str):
    try:
        return int(value)
    except ValueError:
        # ИСПРАВЛЕНО (B110): ошибка логируется, а не молча игнорируется
        log.warning("cannot parse %r as int", value)
        return None
