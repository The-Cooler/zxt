from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import WebPageSnapshot

NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".nav",
    ".navbar",
    ".menu",
    ".sidebar",
    ".footer",
    ".header",
    ".breadcrumb",
    ".advertisement",
    ".ads",
    ".cookie",
    ".popup",
)


def _normalize_text(value: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", value).strip()


def _page_filename(snapshot: WebPageSnapshot) -> str:
    parsed = urlparse(snapshot.final_url or snapshot.url)
    name = snapshot.title.strip() or parsed.path.strip("/").split("/")[-1] or parsed.hostname or "web-page"
    safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", name).strip("-._")
    return f"{safe[:80] or 'web-page'}.md"


def _append_markdown_for_element(lines: list[str], element) -> None:
    name = getattr(element, "name", "")
    text = _normalize_text(element.get_text(" ", strip=True))
    if not text:
        return

    if name in ("h1", "h2", "h3"):
        level = {"h1": "#", "h2": "##", "h3": "###"}[name]
        lines.extend(["", f"{level} {text}"])
        return
    if name in ("li",):
        lines.append(f"- {text}")
        return
    if name in ("pre", "code"):
        lines.extend(["", "```", text, "```"])
        return
    if name in ("p", "blockquote"):
        lines.extend(["", text])


def clean_web_page_to_markdown(snapshot: WebPageSnapshot) -> tuple[str, str]:
    soup = BeautifulSoup(snapshot.html or "", "html.parser")
    for selector in NOISE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    title = snapshot.title.strip()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [f"# {title or snapshot.topic or '网页内容'}", "", f"来源: {snapshot.final_url or snapshot.url}"]

    for element in main.find_all(["h1", "h2", "h3", "p", "li", "pre", "code", "blockquote"]):
        _append_markdown_for_element(lines, element)

    if len(lines) <= 3:
        fallback = _normalize_text(main.get_text(" ", strip=True) or snapshot.text)
        if fallback:
            lines.extend(["", fallback])

    markdown = "\n".join(lines).strip() + "\n"
    return _page_filename(snapshot), markdown
