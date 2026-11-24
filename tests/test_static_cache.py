"""Static-asset cache correctness: a browser must never pair a stale cached
dist-chart.js with freshly rendered fragments (it draws a fixed 800x320 chart
pinned to the SVG's top-left corner — off-center at large windows, clipped at
small ones).

Three layers of defense are covered here:
1. Pages reference /static assets through content-hashed URLs.
2. /static responses carry Cache-Control: no-cache (revalidate, cheap 304s).
3. The SSE "connected" event names the server process so long-open pages
   reload after a redeploy (see base.html).
"""

import re

from fastapi.testclient import TestClient

from bayesian_quiz.app import BOOT_ID, _static_url, app
from bayesian_quiz.state import GameManager, Question, games

SLUG = "static-test"


def make_client() -> TestClient:
    games[SLUG] = GameManager([Question(text="Q1", answer=1.0, scale=10.0)])
    return TestClient(app)


def test_static_url_is_content_hashed():
    url = _static_url("dist-chart.js")
    assert re.fullmatch(r"/static/dist-chart\.js\?v=[0-9a-f]{10}", url)
    # Stable across calls (cached) so every page shares browser cache entries.
    assert _static_url("dist-chart.js") == url


def test_pages_reference_versioned_dist_chart():
    client = make_client()
    for path in (f"/projector?{SLUG}", f"/play?{SLUG}"):
        page = client.get(path).text
        assert re.search(r'src="/static/dist-chart\.js\?v=[0-9a-f]{10}"', page), path


def test_static_responses_require_revalidation():
    client = make_client()
    resp = client.get("/static/dist-chart.js")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert "etag" in resp.headers
    # Conditional refetch is a cheap 304, so no-cache stays affordable.
    resp304 = client.get(
        "/static/dist-chart.js", headers={"if-none-match": resp.headers["etag"]}
    )
    assert resp304.status_code == 304


def test_page_embeds_boot_id_for_reload_check():
    client = make_client()
    page = client.get(f"/projector?{SLUG}").text
    assert BOOT_ID in page
