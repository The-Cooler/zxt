from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from yuxi.knowledge.utils import calculate_content_hash
from yuxi.knowledge.utils.url_fetcher import ALLOWED_CONTENT_TYPES, MAX_DOWNLOAD_SIZE
from yuxi.utils import logger

from .models import WebPageSnapshot

MAX_REDIRECTS = 5
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0 Safari/537.36"
    )
}


async def _is_private_hostname(hostname: str | None) -> bool:
    if not hostname:
        return True
    try:
        ip_list = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except Exception as e:
        logger.warning(f"Failed to resolve hostname {hostname}: {e}")
        return True

    for item in ip_list:
        ip_addr = item[4][0]
        ip_obj = ipaddress.ip_address(ip_addr)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return True
    return False


async def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use HTTP or HTTPS protocol")
    if not parsed.hostname:
        raise ValueError("Invalid URL: no hostname found")
    if await _is_private_hostname(parsed.hostname):
        raise ValueError("Access to private, loopback, or link-local addresses is forbidden")


async def _resolve_final_html_url(url: str) -> str:
    await validate_public_http_url(url)
    current_url = url
    redirect_count = 0

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
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
