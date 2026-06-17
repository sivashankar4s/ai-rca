"""Tests for NavifyLLMProvider."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.providers.llm.navify import NavifyLLMProvider


class TestNavifyLLMProvider:
    def test_init_builds_url_from_base(self) -> None:
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com/"
            provider = NavifyLLMProvider()
        assert provider._url == "http://llm.example.com/v1/chat/completions"

    def test_init_strips_trailing_slash(self) -> None:
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com///"
            provider = NavifyLLMProvider()
        assert provider._url == "http://llm.example.com/v1/chat/completions"

    def test_invoke_raises_when_no_api_key(self) -> None:
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com"
            provider = NavifyLLMProvider()
            s.llm_api_key = ""
            with pytest.raises(RuntimeError, match="LLM_API_KEY is not configured"):
                provider.invoke("hello")

    def test_invoke_raises_when_no_base_url(self) -> None:
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = ""
            provider = NavifyLLMProvider()
            s.llm_api_key = "key"
            with pytest.raises(RuntimeError, match="LLM_BASE_URL is not configured"):
                provider.invoke("hello")

    def test_invoke_returns_content_on_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "result text"}}]}
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com"
            provider = NavifyLLMProvider()
            s.llm_api_key = "key"
            s.llm_model = "navify-v1"
            with patch("backend.providers.llm.navify.requests.post", return_value=mock_resp):
                result = provider.invoke("test prompt")
        assert result == "result text"

    def test_invoke_raises_on_http_error(self) -> None:
        error_resp = MagicMock()
        error_resp.status_code = 429
        http_err = requests.exceptions.HTTPError(response=error_resp)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = http_err
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com"
            provider = NavifyLLMProvider()
            s.llm_api_key = "key"
            s.llm_model = "navify-v1"
            with patch("backend.providers.llm.navify.requests.post", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="429"):
                    provider.invoke("test")

    def test_invoke_raises_on_connection_error(self) -> None:
        conn_err = requests.exceptions.ConnectionError("refused")
        with patch("backend.providers.llm.navify.settings") as s:
            s.llm_base_url = "http://llm.example.com"
            provider = NavifyLLMProvider()
            s.llm_api_key = "key"
            s.llm_model = "navify-v1"
            with patch("backend.providers.llm.navify.requests.post", side_effect=conn_err):
                with pytest.raises(RuntimeError, match="Cannot connect"):
                    provider.invoke("test")
