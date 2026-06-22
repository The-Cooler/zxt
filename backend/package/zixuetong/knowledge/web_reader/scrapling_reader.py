from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from zixuetong.knowledge.utils import calculate_content_hash
from zixuetong.utils import logger

from .models import WebPageSnapshot

# 最大允许下载大小 (10MB)
MAX_DOWNLOAD_SIZE = 10 * 1024 * 1024
# 允许的 Content-Type
ALLOWED_CONTENT_TYPES = ["text/html", "application/xhtml+xml"]

MAX_REDIRECTS = 5
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0 Safari/537.36"
    )
}


async def _is_private_hostname(hostname: str | None) -> bool:
    """检查主机名是否解析到私有 IP 地址。

    只阻止明确的内网地址（localhost、192.168.x.x 等）。
    特殊保留地址（如 198.18.x.x 用于 VPN/代理）将被允许。
    """
    if not hostname:
        return True
    try:
        ip_list = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except Exception as e:
        logger.warning(f"Failed to resolve hostname {hostname}: {e}")
        # DNS 解析失败时，允许继续尝试
        return False

    for item in ip_list:
        ip_addr = item[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_addr)

            # 只阻止明确的私有地址
            if ip_obj.is_loopback:
                # 127.0.0.0/8 - 本地回环
                logger.info(f"Blocked loopback address: {ip_addr}")
                return True
            if ip_obj.is_link_local:
                # 169.254.0.0/16 - 链路本地地址
                logger.info(f"Blocked link-local address: {ip_addr}")
                return True

            # 检查内网私有地址段
            if ip_obj.version == 4:
                private_networks = [
                    ipaddress.ip_network('10.0.0.0/8'),      # Class A 私有地址
                    ipaddress.ip_network('172.16.0.0/12'),   # Class B 私有地址
                    ipaddress.ip_network('192.168.0.0/16'),  # Class C 私有地址
                ]
                for network in private_networks:
                    if ip_obj in network:
                        logger.info(f"Blocked private network address: {ip_addr}")
                        return True

            # 允许 198.18.0.0/15 等特殊保留地址（可能用于 VPN/代理）

        except ValueError:
            continue

    return False


async def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL 必须使用 HTTP 或 HTTPS 协议")
    if not parsed.hostname:
        raise ValueError("无效的 URL：无法找到主机名")
    if await _is_private_hostname(parsed.hostname):
        raise ValueError(
            "禁止访问私有地址、回环地址或本地地址。"
            "请使用公网可访问的 URL，例如 https://example.com"
        )


async def _resolve_final_html_url(url: str) -> str:
    await validate_public_http_url(url)
    current_url = url
    redirect_count = 0

    # 明确禁用代理，直接连接目标服务器
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, proxy=None) as client:
        while True:
            async with client.stream("GET", current_url, headers=REQUEST_HEADERS) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if redirect_count >= MAX_REDIRECTS:
                        raise ValueError("Too many redirects")
                    redirect_count += 1
                    location = response.headers.get("Location")
                    if not location:
                        raise ValueError("Redirect response missing Location header")
                    current_url = urljoin(current_url, location)
                    await validate_public_http_url(current_url)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if not any(allowed in content_type for allowed in ALLOWED_CONTENT_TYPES):
                    raise ValueError(f"Unsupported Content-Type: {content_type}. Only HTML is supported.")
                return current_url


def _coerce_response_html(response) -> str:
    for attr in ("body", "raw_body", "content", "html_content", "html", "text"):
        if not hasattr(response, attr):
            continue
        value = getattr(response, attr)
        if callable(value):
            try:
                value = value()
            except TypeError:
                continue
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            return value
    return str(response)


def _extract_topic(soup: BeautifulSoup, title: str, text: str) -> str:
    if title:
        return title[:120]
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(" ", strip=True)
        if h1_text:
            return h1_text[:120]
    return text[:60]


def _extract_same_domain_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    base = urlparse(base_url)
    seen: set[str] = set()
    links: list[str] = []

    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        normalized, _fragment = urldefrag(urljoin(base_url, href))
        parsed = urlparse(normalized)
        if parsed.scheme not in ("http", "https"):
            continue
        if (parsed.hostname or "").lower() != (base.hostname or "").lower():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)

    return links


class ScraplingWebReader:
    async def fetch_page(self, url: str, *, depth: int = 0, parent_url: str | None = None) -> WebPageSnapshot:
        final_url = await _resolve_final_html_url(url)

        try:
            from scrapling.fetchers import AsyncFetcher
        except ImportError as e:
            raise ValueError("scrapling[fetchers] dependency is required for web reader") from e

        response = await AsyncFetcher.get(final_url, headers=REQUEST_HEADERS, timeout=30)
        html = _coerce_response_html(response)
        html_bytes = html.encode("utf-8", errors="replace")
        if len(html_bytes) > MAX_DOWNLOAD_SIZE:
            raise ValueError(f"Content size exceeds limit of {MAX_DOWNLOAD_SIZE} bytes")

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        text = soup.get_text(" ", strip=True)
        links = _extract_same_domain_links(soup, final_url)
        content_hash = await calculate_content_hash(html_bytes)

        return WebPageSnapshot(
            url=url,
            final_url=final_url,
            title=title,
            topic=_extract_topic(soup, title, text),
            text=text,
            html=html,
            content_hash=content_hash,
            links=links,
            depth=depth,
            parent_url=parent_url,
        )
