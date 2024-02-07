import os
import pytest
import tempfile

from helm.common.cache import SqliteCacheConfig
from helm.common.request import Request

from .together_client import TogetherClient, TogetherClientError


class TestTogetherClient:
    def setup_method(self, method):
        cache_file = tempfile.NamedTemporaryFile(delete=False)
        self.cache_path: str = cache_file.name

    def teardown_method(self, method):
        os.remove(self.cache_path)

    @pytest.mark.parametrize(
        "together_model,test_input,expected",
        [
            (
                "togethercomputer/RedPajama-INCITE-Base-3B-v1",
                Request(
                    model="together/redpajama-incite-base-3b-v1",
                    model_deployment="together/redpajama-incite-base-3b-v1",
                ),
                {
                    "best_of": 1,
                    "echo": False,
                    "max_tokens": 100,
                    "model": "togethercomputer/RedPajama-INCITE-Base-3B-v1",
                    "n": 1,
                    "prompt": "",
                    "request_type": "language-model-inference",
                    "stop": None,
                    "temperature": 1.0,
                    "top_p": 1,
                },
            ),
            (
                "huggyllama/llama-7b",
                Request(
                    model="meta/llama-7b",
                    model_deployment="together/llama-7b",
                    prompt="I am a computer scientist.",
                    temperature=0,
                    num_completions=4,
                    max_tokens=24,
                    top_k_per_token=3,
                    stop_sequences=["\n"],
                    echo_prompt=True,
                    top_p=0.3,
                ),
                {
                    "best_of": 3,
                    "echo": True,
                    "max_tokens": 24,
                    "model": "huggyllama/llama-7b",
                    "n": 4,
                    "prompt": "I am a computer scientist.",
                    "request_type": "language-model-inference",
                    "stop": ["\n"],
                    "temperature": 0,
                    "top_p": 0.3,
                },
            ),
            (
                "togethercomputer/alpaca-7b",
                Request(
                    model="stanford/alpaca-7b",
                    model_deployment="together/alpaca-7b",
                    stop_sequences=["\n"],
                ),
                {
                    "best_of": 1,
                    "echo": False,
                    "max_tokens": 100,
                    "model": "togethercomputer/alpaca-7b",
                    "n": 1,
                    "prompt": "",
                    "request_type": "language-model-inference",
                    "stop": ["\n", "</s>"],
                    "temperature": 1.0,
                    "top_p": 1,
                },
            ),
            # TODO(#1828): Add test for `SET_DETAILS_TO_TRUE` after Together supports it.
        ],
    )
    def test_convert_to_raw_request(self, together_model, test_input, expected):
        client = TogetherClient(
            cache_config=SqliteCacheConfig(self.cache_path),
            together_model=together_model,
        )
        assert expected == client.convert_to_raw_request(test_input)

    def test_api_key_error(self):
        client = TogetherClient(
            cache_config=SqliteCacheConfig(self.cache_path),
            together_model="togethercomputer/RedPajama-INCITE-Base-3B-v1",
        )
        with pytest.raises(TogetherClientError):
            client.make_request(
                Request(
                    model="together/redpajama-incite-base-3b-v1",
                    model_deployment="together/redpajama-incite-base-3b-v1",
                )
            )
