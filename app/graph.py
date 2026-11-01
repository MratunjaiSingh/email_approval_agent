"""
Flow:
START -> draft_email -> validate -> (issues & retries left? -> draft_email)
                                 -> human_review (interrupt)
human_review -> approved?  yes -> send_email -> END
                           no  -> draft_email (with feedback)
"""
from typing import Callable, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .dates import date_facts
from .state import MailState
from .validators import split_subject, validate_draft

MAX_AUTO_RETRIES = 2
APPROVE_WORDS = {"approved", "approve", "ok", "yes", "y", "send"}

RULES = """You write short, professional emails.
Rules:
- First line must be exactly: Subject: <subject>
- Then a blank line, then the email body.
- Use ONLY the facts given below. Never use placeholders like [Name].
- If dates are provided, copy them exactly as given (weekday included).
- Sign off with the sender name."""


def _to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some providers return content blocks
        return "".join(
            b if isinstance(b, str) else b.get("text", "") for b in content
        )
    return str(content)


def build_prompt(state: MailState) -> str:
    parts = [RULES, f"\nTask: {state.query}"]
    if state.sender_name:
        parts.append(f"Sender name: {state.sender_name}")
    if state.recipient_name:
        parts.append(f"Recipient name: {state.recipient_name}")
    facts = date_facts(state.start_date, state.end_date)
    if facts:
        parts.append(f"\nDate facts (verified, use exactly):\n{facts}")
    if state.draft and (state.human_feedback or state.issues):
        parts.append(f"\nPrevious draft:\n{state.draft}")
    if state.issues:
        parts.append("\nFix these problems:\n- " + "\n- ".join(state.issues))
    if state.human_feedback:
        parts.append(f"\nApply this human feedback:\n{state.human_feedback}")
    return "\n".join(parts)


def build_graph(llm, mailer: Callable[[str, str, str], None], checkpointer):
    """llm and mailer are injected, so tests can pass fakes."""

    def draft_email(state: MailState):
        text = _to_text(llm.invoke(build_prompt(state)).content).strip()
        return {
            "draft": text,
            "human_feedback": "",
            "attempts": state.attempts + 1,
        }

    def validate(state: MailState):
        return {
            "issues": validate_draft(
                state.draft, state.sender_name, state.start_date, state.end_date
            )
        }

    def after_validate(state: MailState) -> Literal["draft_email", "human_review"]:
        if state.issues and state.attempts <= MAX_AUTO_RETRIES:
            return "draft_email"
        return "human_review"

    def human_review(state: MailState):
        answer = interrupt(
            {
                "draft": state.draft,
                "issues": state.issues,
                "question": "Approve this draft, or give feedback for a rewrite?",
            }
        )
        if isinstance(answer, str):  # a plain string also works (handy in notebooks)
            answer = (
                {"approved": True}
                if answer.strip().lower() in APPROVE_WORDS
                else {"approved": False, "feedback": answer}
            )
        if answer.get("approved"):
            return {"approved": True, "human_feedback": ""}
        return {
            "approved": False,
            "human_feedback": (answer.get("feedback") or "").strip(),
            "issues": [],
            "attempts": 0,
        }

    def after_review(state: MailState) -> Literal["send_email", "draft_email"]:
        return "send_email" if state.approved else "draft_email"

    def send_email(state: MailState):
        # last guardrail: an invalid draft is never sent, even after approval
        issues = validate_draft(
            state.draft, state.sender_name, state.start_date, state.end_date
        )
        if issues:
            return {
                "status": "blocked",
                "issues": issues,
                "final_response": "Blocked: " + " ".join(issues),
            }
        subject, body = split_subject(state.draft)
        try:
            mailer(state.to_email, subject, body)
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "final_response": f"Send failed: {exc}"}
        return {"status": "sent", "final_response": f"Email sent to {state.to_email}"}

    g = StateGraph(MailState)
    g.add_node("draft_email", draft_email)
    g.add_node("validate", validate)
    g.add_node("human_review", human_review)
    g.add_node("send_email", send_email)

    g.add_edge(START, "draft_email")
    g.add_edge("draft_email", "validate")
    g.add_conditional_edges("validate", after_validate)
    g.add_conditional_edges("human_review", after_review)
    g.add_edge("send_email", END)

    return g.compile(checkpointer=checkpointer)
