import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain.chat_models import init_chat_model
from openai import AuthenticationError

import env_utils


ROOT = Path(__file__).resolve().parent


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "TAVILY_API_KEY": "tool-test-key"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def check_output(self):
        output = io.StringIO()
        with redirect_stdout(output):
            env_utils.doublecheck_env(str(ROOT / "example.env"))
        return output.getvalue()

    def test_direct_default_and_false_flags(self):
        for flag in (None, "", "false", "False", "0", "no"):
            with self.subTest(flag=flag):
                if flag is None:
                    os.environ.pop("LANGSMITH_GATEWAY", None)
                else:
                    os.environ["LANGSMITH_GATEWAY"] = flag
                os.environ["LANGSMITH_GATEWAY_API_KEY"] = "gateway-test-key"
                self.assertIn("OPENAI_API_KEY is required", self.check_output())
                os.environ["OPENAI_API_KEY"] = "direct-test-key"
                self.assertNotIn("Issues found:", self.check_output())
                del os.environ["OPENAI_API_KEY"]

    def test_gateway_fallback_and_override_without_provider_keys(self):
        os.environ.update(LANGSMITH_GATEWAY="true", LANGSMITH_API_KEY="tracing-test-key")
        self.assertNotIn("Issues found:", self.check_output())
        del os.environ["LANGSMITH_API_KEY"]
        os.environ["LANGSMITH_GATEWAY_API_KEY"] = "gateway-test-key"
        self.assertNotIn("Issues found:", self.check_output())
        os.environ["LANGSMITH_TRACING"] = "true"
        self.assertIn("LANGSMITH_API_KEY is required", self.check_output())

    def test_missing_empty_and_placeholder_credentials(self):
        for gateway in (False, True):
            os.environ["LANGSMITH_GATEWAY"] = str(gateway).lower()
            key = "LANGSMITH_API_KEY" if gateway else "OPENAI_API_KEY"
            for value in (None, "", " ", "your-key", "your_key_here", "****", "lsv2_..."):
                with self.subTest(gateway=gateway, value=value):
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                    self.assertIn(f"{key} is required", self.check_output())

    def test_placeholder_override_is_not_replaced_by_fallback(self):
        os.environ.update(LANGSMITH_GATEWAY="true", LANGSMITH_API_KEY="fallback-test-key",
                          LANGSMITH_GATEWAY_API_KEY="your-key")
        self.assertIn("LANGSMITH_GATEWAY_API_KEY is required", self.check_output())
        os.environ["LANGSMITH_GATEWAY_API_KEY"] = ""
        self.assertNotIn("Issues found:", self.check_output())

    def test_invalid_gateway_and_provider_url_override(self):
        os.environ.update(LANGSMITH_GATEWAY="off", LANGSMITH_API_KEY="gateway-test-key")
        self.assertIn("LANGSMITH_GATEWAY must be true or a gateway base URL", self.check_output())
        os.environ.update(LANGSMITH_GATEWAY="true", OPENAI_BASE_URL="https://api.openai.com/v1")
        self.assertIn("OPENAI_BASE_URL overrides automatic gateway routing", self.check_output())

    def test_dotenv_uses_repository_precedence(self):
        os.environ["LANGSMITH_GATEWAY"] = "false"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("LANGSMITH_GATEWAY=true\nLANGSMITH_API_KEY=gateway-test-key\n")
            env_utils.load_dotenv(path, override=False)
        self.assertEqual(env_utils._gateway_enabled(), False)

    def test_successful_gateway_request_and_invalid_authentication(self):
        os.environ.update(LANGSMITH_GATEWAY="https://eu.gateway.smith.langchain.com/",
                          LANGSMITH_API_KEY="fallback-test-key",
                          LANGSMITH_GATEWAY_API_KEY="gateway-test-key")
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"id": "chatcmpl-test", "object": "chat.completion",
                "created": 0, "model": "gpt-5-nano", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": "gateway chat works"},
                "finish_reason": "stop"}]})

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            model = init_chat_model("openai:gpt-5-nano", http_client=client,
                                    use_responses_api=False, max_retries=0)
            self.assertEqual(model.invoke("ping").content, "gateway chat works")
        self.assertEqual(str(requests[0].url),
                         "https://eu.gateway.smith.langchain.com/openai/v1/chat/completions")
        self.assertEqual(requests[0].headers["authorization"], "Bearer gateway-test-key")
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
                401, json={"error": {"message": "Invalid API key", "type": "authentication_error"}}))) as client:
            model = init_chat_model("openai:gpt-5-nano", http_client=client,
                                    use_responses_api=False, max_retries=0)
            with self.assertRaises(AuthenticationError):
                model.invoke("ping")

    def test_sdk_uses_direct_auth_for_disabled_gateway(self):
        for flag in ("", "false", "0", "no"):
            with self.subTest(flag=flag):
                os.environ.update(LANGSMITH_GATEWAY=flag, OPENAI_API_KEY="direct-test-key",
                                  LANGSMITH_GATEWAY_API_KEY="gateway-test-key")
                model = init_chat_model("openai:gpt-5-nano")
                self.assertEqual(model.openai_api_key.get_secret_value(), "direct-test-key")
                self.assertIsNone(model.openai_api_base)

    def test_tools_still_required_and_embeddings_advisory_is_scoped(self):
        from langchain_openai import OpenAIEmbeddings
        from openai import OpenAIError

        os.environ.update(LANGSMITH_GATEWAY="true", LANGSMITH_API_KEY="gateway-test-key")
        output = self.check_output()
        self.assertNotIn("Issues found:", output)
        self.assertIn("Bonus RAG only", output)
        with self.assertRaises(OpenAIError):
            OpenAIEmbeddings(model="text-embedding-3-large")
        del os.environ["TAVILY_API_KEY"]
        self.assertIn("TAVILY_API_KEY is required", self.check_output())

    def test_optional_chat_integrations_resolve_gateway_without_provider_keys(self):
        from langchain_anthropic import ChatAnthropic
        from langchain_google_genai import ChatGoogleGenerativeAI

        os.environ.update(LANGSMITH_GATEWAY="true", LANGSMITH_API_KEY="gateway-test-key")
        anthropic = ChatAnthropic(model="claude-sonnet-4-5")
        self.assertEqual(anthropic.anthropic_api_url,
                         "https://gateway.smith.langchain.com/anthropic")
        self.assertEqual(anthropic.anthropic_api_key.get_secret_value(), "gateway-test-key")
        google = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")
        self.assertEqual(google.base_url, "https://gateway.smith.langchain.com/gemini")
        self.assertEqual(google.google_api_key.get_secret_value(), "gateway-test-key")


if __name__ == "__main__":
    unittest.main()
