import sqlite3
import uuid
from datetime import date
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, EmailStr, model_validator

from .config import checkpoint_db, get_llm, get_mailer
from .graph import build_graph

app = FastAPI(title="Email Approval Agent", version="1.0.0")


@lru_cache
def get_graph():
    conn = sqlite3.connect(checkpoint_db(), check_same_thread=False)
    return build_graph(get_llm(), get_mailer(), SqliteSaver(conn))


# ---------- schemas ----------
class DraftRequest(BaseModel):
    query: str
    to_email: EmailStr
    sender_name: str
    recipient_name: str = ""
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date and not self.start_date:
            raise ValueError("start_date is required when end_date is given")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ResumeRequest(BaseModel):
    decision: Literal["approve", "revise"]
    feedback: str = ""

    @model_validator(mode="after")
    def _fb(self):
        if self.decision == "revise" and not self.feedback.strip():
            raise ValueError("feedback is required when decision is revise")
        return self


class DraftResponse(BaseModel):
    thread_id: str
    status: Literal["awaiting_approval", "sent", "blocked", "failed", "drafting"]
    draft: str = ""
    issues: list[str] = []
    final_response: str = ""


# ---------- helpers ----------
def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _snapshot_response(graph, thread_id: str) -> DraftResponse:
    snap = graph.get_state(_cfg(thread_id))
    values = snap.values
    if not isinstance(values, dict):
        values = values.model_dump() if values else {}
    if not values:
        raise HTTPException(404, "Thread not found")

    waiting = any(t.interrupts for t in snap.tasks)
    return DraftResponse(
        thread_id=thread_id,
        status="awaiting_approval" if waiting else values.get("status", "drafting"),
        draft=values.get("draft", ""),
        issues=values.get("issues", []),
        final_response=values.get("final_response", ""),
    )


def _run(graph, payload, thread_id: str) -> DraftResponse:
    try:
        graph.invoke(payload, config=_cfg(thread_id))
    except HTTPException:
        raise
    except Exception as exc:  # LLM/network failure
        raise HTTPException(502, f"agent error: {exc}") from exc
    return _snapshot_response(graph, thread_id)


# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/drafts", response_model=DraftResponse)
def create_draft(req: DraftRequest):
    graph = get_graph()
    thread_id = uuid.uuid4().hex
    state_in = {
        "query": req.query,
        "to_email": req.to_email,
        "sender_name": req.sender_name,
        "recipient_name": req.recipient_name,
        "start_date": req.start_date.isoformat() if req.start_date else "",
        "end_date": req.end_date.isoformat() if req.end_date else "",
    }
    return _run(graph, state_in, thread_id)


@app.get("/drafts/{thread_id}", response_model=DraftResponse)
def get_draft(thread_id: str):
    return _snapshot_response(get_graph(), thread_id)


@app.post("/drafts/{thread_id}/resume", response_model=DraftResponse)
def resume(thread_id: str, req: ResumeRequest):
    graph = get_graph()
    current = _snapshot_response(graph, thread_id)
    if current.status != "awaiting_approval":
        raise HTTPException(409, f"Thread is already '{current.status}' and cannot be resumed")
    answer = (
        {"approved": True}
        if req.decision == "approve"
        else {"approved": False, "feedback": req.feedback}
    )
    return _run(graph, Command(resume=answer), thread_id)
