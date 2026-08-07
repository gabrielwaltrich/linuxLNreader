from novel_reader.services.downloader import DownloadedPage
from novel_reader.sources.generic import GenericHtmlSource
from novel_reader.sources.manager import SourceManager
from novel_reader.sources.webnovel import WebNovelSource


def test_manager_selects_webnovel():
    manager = SourceManager()
    assert isinstance(manager.source_for("https://www.webnovel.com/book/x"), WebNovelSource)


def test_webnovel_requires_browser():
    manager = SourceManager()
    assert manager.requires_browser("https://www.webnovel.com/book/x") is True


def test_generic_does_not_require_browser():
    manager = SourceManager()
    assert manager.requires_browser("https://example.org/chapter/1") is False


def test_manager_falls_back_to_generic_html():
    manager = SourceManager()
    assert isinstance(manager.source_for("https://example.org/chapter/1"), GenericHtmlSource)


def test_generic_parser_extracts_article():
    html = """
    <html><head><title>Chapter One</title></head><body>
      <article>
        <h1>Chapter One</h1>
        <p>This is a deliberately long paragraph containing enough text for the parser to identify it as chapter content for an offline test.</p>
        <p>This is another deliberately long paragraph so the resulting chapter easily exceeds the parser's minimum content threshold.</p>
      </article>
      <a rel="next" href="/chapter/2">Next</a>
    </body></html>
    """
    page = DownloadedPage(
        requested_url="https://example.org/chapter/1",
        final_url="https://example.org/chapter/1",
        html=html,
        status_code=200,
    )
    chapter = GenericHtmlSource().parse(page)
    assert chapter.chapter_title == "Chapter One"
    assert "deliberately long paragraph" in chapter.text
    assert chapter.next_url == "https://example.org/chapter/2"


def test_manager_parses_rendered_html():
    html = """
    <html><head><title>Rendered Chapter</title></head><body>
      <article>
        <h1>Rendered Chapter</h1>
        <p>This rendered paragraph is intentionally long enough for the generic parser to recognize it as useful chapter content after JavaScript rendering.</p>
        <p>A second rendered paragraph makes sure the parser has enough material to pass its minimum text threshold during this test.</p>
      </article>
    </body></html>
    """
    chapter = SourceManager().parse_rendered_html(
        requested_url="https://example.org/rendered/1",
        final_url="https://example.org/rendered/1",
        html=html,
    )
    assert chapter.chapter_title == "Rendered Chapter"
    assert "second rendered paragraph" in chapter.text


def test_webnovel_does_not_flag_global_batch_unlock_text_when_chapter_exists():
    html = """
    <html><head><title>Chapter 39</title></head><body>
      <article>
        <h1>Chapter 39</h1>
        <p>This is a sufficiently long chapter paragraph with real story text. It exists to verify that global unlock-related user-interface labels do not make a free chapter look restricted.</p>
        <p>This is the second sufficiently long story paragraph, adding enough legitimate reading content to exceed the parser minimum and complete the regression test successfully.</p>
        <p>This is a third story paragraph included so the combined chapter body is clearly longer than three hundred characters and cannot be mistaken for a short interface fragment.</p>
      </article>
      <aside><h4>Batch unlock chapters</h4></aside>
    </body></html>
    """
    page = DownloadedPage(
        requested_url="https://www.webnovel.com/book/1/2",
        final_url="https://www.webnovel.com/book/1/2",
        html=html,
        status_code=200,
    )
    chapter = WebNovelSource().parse(page)
    assert "real story text" in chapter.text
    assert chapter.source == "WebNovel"


def test_webnovel_reports_restricted_only_without_chapter_content():
    from novel_reader.errors import AccessRestrictedError

    html = """
    <html><head><title>Locked</title></head><body>
      <div class="chapter-locked"><p>Use coins to unlock this chapter</p></div>
    </body></html>
    """
    page = DownloadedPage(
        requested_url="https://www.webnovel.com/book/1/3",
        final_url="https://www.webnovel.com/book/1/3",
        html=html,
        status_code=200,
    )
    try:
        WebNovelSource().parse(page)
    except AccessRestrictedError:
        pass
    else:
        raise AssertionError("Expected AccessRestrictedError")
