import pytest

from yuxi.knowledge.web_reader import scrapling_reader


def test_extract_same_domain_links_normalizes_and_deduplicates():
    soup = scrapling_reader.BeautifulSoup(
        """
        <html>
          <body>
            <a href="/a#frag">A</a>
            <a href="https://example.com/a">A duplicate</a>
            <a href="https://example.com/b?x=1#top">B</a>
            <a href="https://other.example.com/c">Other</a>
            <a href="mailto:test@example.com">Mail</a>
          </body>
        </html>
        """,
        "html.parser",
    )

    links = scrapling_reader._extract_same_domain_links(soup, "https://example.com/root")

    assert links == ["https://example.com/a", "https://example.com/b?x=1"]


def test_coerce_response_html_prefers_raw_html_body_over_text():
    class FakeResponse:
        text = "plain text without links"
        body = b"""
        <html>
          <head><title>CLI Reference</title></head>
          <body><a href="/latest/cli-reference/config/">Config</a></body>
        </html>
        """

    html = scrapling_reader._coerce_response_html(FakeResponse())
    soup = scrapling_reader.BeautifulSoup(html, "html.parser")

    assert soup.title.get_text(strip=True) == "CLI Reference"
    assert scrapling_reader._extract_same_domain_links(
        soup,
        "https://docs.jj-vcs.dev/latest/cli-reference/",
    ) == ["https://docs.jj-vcs.dev/latest/cli-reference/config/"]


@pytest.mark.asyncio
async def test_validate_public_http_url_rejects_private_ip(monkeypatch):
    async def fake_private_hostname(hostname):
        return True

    monkeypatch.setattr(scrapling_reader, "_is_private_hostname", fake_private_hostname)

    with pytest.raises(ValueError, match="private"):
        await scrapling_reader.validate_public_http_url("https://127.0.0.1/page")


@pytest.mark.asyncio
async def test_validate_public_http_url_rejects_non_http():
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        await scrapling_reader.validate_public_http_url("ftp://example.com/file")
