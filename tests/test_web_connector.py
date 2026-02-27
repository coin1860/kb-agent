"""
Tests for WebConnector — URL scraping and markdown conversion.
Run: python -m pytest tests/test_web_connector.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Mock heavy deps
for mod in ["chromadb", "chromadb.config", "chromadb.utils",
            "chromadb.utils.embedding_functions", "sentence_transformers", "ripgrep"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

_mock_audit = MagicMock()
sys.modules["kb_agent.audit"] = _mock_audit

from kb_agent.connectors.web_connector import WebConnector


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Page Title</title></head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<header><h1>Site Header</h1></header>
<main>
  <article>
    <h1>Main Article Title</h1>
    <p>This is the first paragraph with <strong>important</strong> content.</p>
    <p>This is the second paragraph with a <a href="https://example.com">link</a>.</p>
    <ul>
      <li>Item one</li>
      <li>Item two</li>
    </ul>
  </article>
</main>
<footer><p>Copyright 2024</p></footer>
<script>console.log("should be removed");</script>
<style>.hidden { display:none; }</style>
</body>
</html>
"""

SAMPLE_HTML_NO_ARTICLE = """
<html>
<head><title>Simple Page</title></head>
<body>
<div class="content">
  <h2>Section Title</h2>
  <p>Some body content here.</p>
</div>
<nav>nav links</nav>
</body>
</html>
"""


class TestWebConnector:
    @pytest.fixture
    def connector(self):
        return WebConnector()

    def test_fetch_data_success(self, connector):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status = MagicMock()

        with patch("kb_agent.connectors.web_connector.requests.get", return_value=mock_resp):
            results = connector.fetch_data("https://example.com/article")

        assert len(results) == 1
        doc = results[0]
        assert doc["title"] == "Test Page Title"
        assert doc["metadata"]["source"] == "web"
        assert doc["metadata"]["url"] == "https://example.com/article"
        assert doc["metadata"]["domain"] == "example.com"

        # Content should have the article text
        content = doc["content"]
        assert "Main Article Title" in content
        assert "important" in content
        assert "Item one" in content

        # Nav, footer, script, style should be stripped
        assert "Home" not in content
        assert "About" not in content
        assert "Copyright" not in content
        assert "console.log" not in content
        assert ".hidden" not in content

    def test_fetch_data_no_article_tag(self, connector):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML_NO_ARTICLE
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status = MagicMock()

        with patch("kb_agent.connectors.web_connector.requests.get", return_value=mock_resp):
            results = connector.fetch_data("https://example.com/simple")

        assert len(results) == 1
        content = results[0]["content"]
        assert "Section Title" in content
        assert "Some body content" in content

    def test_fetch_data_network_error(self, connector):
        import requests as req
        with patch("kb_agent.connectors.web_connector.requests.get",
                   side_effect=req.ConnectionError("DNS failed")):
            results = connector.fetch_data("https://nonexistent.example.com")

        assert len(results) == 1
        doc = results[0]
        assert "error" in doc["metadata"]
        assert "Error" in doc["content"]

    def test_auto_prepend_https(self, connector):
        mock_resp = MagicMock()
        mock_resp.text = "<html><head><title>T</title></head><body><p>Hello</p></body></html>"
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status = MagicMock()

        with patch("kb_agent.connectors.web_connector.requests.get", return_value=mock_resp) as mock_get:
            connector.fetch_data("example.com")
            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert call_url.startswith("https://")

    def test_url_id_deterministic(self, connector):
        id1 = connector._url_id("https://example.com/page")
        id2 = connector._url_id("https://example.com/page")
        assert id1 == id2
        assert id1.startswith("web_")

    def test_url_id_different_urls(self, connector):
        id1 = connector._url_id("https://example.com/page1")
        id2 = connector._url_id("https://example.com/page2")
        assert id1 != id2

    def test_fetch_all_returns_empty(self, connector):
        assert connector.fetch_all() == []

    def test_strips_cookie_banners(self, connector):
        html = """
        <html><head><title>Test</title></head><body>
        <div class="cookie-banner">Accept cookies</div>
        <div class="content"><p>Real content here</p></div>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status = MagicMock()

        with patch("kb_agent.connectors.web_connector.requests.get", return_value=mock_resp):
            results = connector.fetch_data("https://example.com")

        content = results[0]["content"]
        assert "Accept cookies" not in content
        assert "Real content" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
