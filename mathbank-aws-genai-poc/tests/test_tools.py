import asyncio
import json
from types import SimpleNamespace

from mathbank_genai_poc.knowledge import TopicError
from mathbank_genai_poc.tools import make_tools


class StubKb:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def search(self, topic):
        if self.error:
            raise self.error
        return self.result


RESULT = {"topic": "inversion", "grounded": True, "source": "S3 Vectors",
          "concepts": [{"id": "T", "name": "Inversion"}], "practice_problems": [],
          "teaching_moves": [{"guidance": "PRIVATE NOTE"}]}


def run(kb, topic="inversion"):
    sent = []

    async def notify(payload):
        sent.append(payload)

    tool = make_tools(kb)[0]
    context = SimpleNamespace(invocation_state={"on_sources": notify})
    result = asyncio.run(tool._tool_func(topic=topic, tool_context=context))
    return result, sent


def test_model_gets_private_moves_but_browser_does_not():
    result, sent = run(StubKb(RESULT))
    body = json.loads(result["content"][0]["text"])
    assert result["status"] == "success" and body["teaching_moves"][0]["guidance"] == "PRIVATE NOTE"
    assert "never read them aloud" in body["guidance"]
    assert sent == [{"topic": "inversion", "grounded": True, "source": "S3 Vectors",
                     "concepts": [{"id": "T", "name": "Inversion"}], "practice_problems": [], "teaching_moves": 1}]


def test_failures_are_sanitized():
    result, sent = run(StubKb(error=RuntimeError("arn:aws:secret-detail")))
    assert result["status"] == "error" and "secret-detail" not in json.dumps(result) + json.dumps(sent)
    assert sent[0]["grounded"] is False


def test_invalid_topic_is_reported_without_notifying():
    result, sent = run(StubKb(error=TopicError("topic must be 2-300 characters")))
    assert result["status"] == "error" and sent == []


def test_tool_spec_names_the_topic_parameter():
    spec = make_tools(StubKb(RESULT))[0].tool_spec
    assert spec["name"] == "search_math_topic"
    assert list(spec["inputSchema"]["json"]["properties"]) == ["topic"]
