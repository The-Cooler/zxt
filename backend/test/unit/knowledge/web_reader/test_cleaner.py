from zixuetong.knowledge.web_reader.cleaner import clean_web_page_to_markdown
from zixuetong.knowledge.web_reader.models import WebPageSnapshot


def test_clean_web_page_to_markdown_keeps_article_text_and_removes_navigation():
    snapshot = WebPageSnapshot(
        url="https://example.com/docs/page",
        final_url="https://example.com/docs/page",
        title="Docs Page",
        html="""
        <html>
          <body>
            <nav>Global menu</nav>
            <article>
              <h1>Docs Page</h1>
              <p>Useful introduction.</p>
              <ul><li>First point</li></ul>
            </article>
            <footer>Copyright</footer>
          </body>
        </html>
        """,
        text="Global menu Docs Page Useful introduction First point Copyright",
    )

    filename, markdown = clean_web_page_to_markdown(snapshot)

    assert filename == "Docs-Page.md"
    assert "# Docs Page" in markdown
    assert "Useful introduction." in markdown
    assert "- First point" in markdown
    assert "Global menu" not in markdown
    assert "Copyright" not in markdown
