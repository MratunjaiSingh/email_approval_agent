from types import SimpleNamespace

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph import build_graph

GOOD = "Subject: Medical leave\n\nDear Sir,\nI need leave from Monday, 2 November 2026 to Friday, 6 November 2026.\n\nRegards,\nMratunjai"
BAD = "Subject: Leave\n\nDear [Supervisor's Name],\nPlease approve.\n\nRegards,\nMratunjai"

INPUT = {
    "query": "medical leave email",
    "to_email": "boss@example.com",
    "sender_name": "Mratunjai",
    "start_date": "2026-11-02",
    "end_date": "2026-11-06",
}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.replies.pop(0))


def make(replies):
    sent, llm = [], FakeLLM(replies)
    graph = build_graph(llm, lambda to, s, b: sent.append((to, s, b)), InMemorySaver())
    return graph, llm, sent, {"configurable": {"thread_id": "t1"}}


def waiting(graph, cfg):
    return any(t.interrupts for t in graph.get_state(cfg).tasks)


def test_happy_path_sends_only_after_approval():
    graph, _, sent, cfg = make([GOOD])
    graph.invoke(INPUT, cfg)
    assert waiting(graph, cfg) and sent == []          # approval se pehle koi send nahi
    out = graph.invoke(Command(resume={"approved": True}), cfg)
    assert out["status"] == "sent" and len(sent) == 1
    assert sent[0][0] == "boss@example.com"


def test_revise_loop_uses_feedback():
    graph, llm, sent, cfg = make([GOOD, GOOD])
    graph.invoke(INPUT, cfg)
    graph.invoke(Command(resume={"approved": False, "feedback": "make it shorter"}), cfg)
    assert "make it shorter" in llm.prompts[1]
    assert waiting(graph, cfg) and sent == []
    out = graph.invoke(Command(resume={"approved": True}), cfg)
    assert out["status"] == "sent"


def test_validator_auto_retries_bad_draft():
    graph, llm, _, cfg = make([BAD, GOOD])
    graph.invoke(INPUT, cfg)
    assert "Remove placeholders" in llm.prompts[1]
    assert graph.get_state(cfg).values["draft"] == GOOD


def test_placeholder_draft_is_blocked_even_if_approved():
    graph, _, sent, cfg = make([BAD, BAD, BAD])
    graph.invoke(INPUT, cfg)
    out = graph.invoke(Command(resume={"approved": True}), cfg)
    assert out["status"] == "blocked" and sent == []


def test_string_resume_still_works_for_notebook():
    graph, _, sent, cfg = make([GOOD])
    graph.invoke(INPUT, cfg)
    out = graph.invoke(Command(resume="yes"), cfg)
    assert out["status"] == "sent"
