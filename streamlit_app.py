"""UI for the Email Approval Agent.  Start everything with: python run.py"""
import datetime as dt
import html

import requests
import streamlit as st

st.set_page_config(page_title="Email Approval Agent", page_icon="✉️", layout="centered")

# Brand colour is read from .streamlit/config.toml (primaryColor), so you only change it there.
BRAND = st.get_option("theme.primaryColor") or "#7A1F2B"

st.markdown(
    """
<style>
.block-container {max-width: 760px; padding-top: 2.5rem;}
h1 {font-weight: 700; border-bottom: 2px solid __BRAND__; padding-bottom: .4rem;}
.paper {
    background: #FFFFFF; border: 1px solid #D9D2C5; border-radius: 4px;
    padding: 28px 34px; margin: 6px 0 18px 0; box-shadow: 0 1px 4px rgba(0,0,0,.08);
    font-family: Georgia, 'Times New Roman', serif; line-height: 1.7; color: #1B1B1B;
}
.paper .meta {color: #6B6458; font-size: .9rem; margin-bottom: 4px;}
.paper .subject {
    font-weight: 700; font-size: 1.05rem; margin: 10px 0 18px 0;
    padding-bottom: 12px; border-bottom: 1px solid #E5DFD3;
}
.badge {
    display: inline-block; padding: 2px 12px; border-radius: 12px;
    font-size: .8rem; letter-spacing: .4px; text-transform: uppercase; border: 1px solid;
}
.badge.waiting {color: #8A5A00; background: #FFF4D6; border-color: #E8CC85;}
.badge.sent    {color: #1E5C2E; background: #E6F2E8; border-color: #A9CFB1;}
.badge.bad     {color: #8B1E1E; background: #F8E4E4; border-color: #DDA8A8;}
.thread {color: #8C8577; font-size: .8rem; margin-left: 10px;}
</style>
""".replace("__BRAND__", BRAND),
    unsafe_allow_html=True,
)

st.title("Email Approval Agent")
st.caption("The AI drafts the email. Nothing is sent until you approve it.")

with st.sidebar.expander("Settings"):
    API = st.text_input("API URL", "http://127.0.0.1:8000").rstrip("/")

ss = st.session_state
ss.setdefault("res", None)
ss.setdefault("to", "")

if st.sidebar.button("New email"):
    ss.res = None
    st.rerun()


def call(method: str, path: str, **kw):
    try:
        r = requests.request(method, f"{API}{path}", timeout=120, **kw)
    except requests.RequestException as e:
        st.error(f"Could not reach the API. Is the server running? ({e})")
        return None
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        st.error(f"Error {r.status_code}: {detail}")
        return None
    return r.json()


def split_subject(draft: str) -> tuple[str, str]:
    lines = draft.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        return lines[0].split(":", 1)[1].strip(), "\n".join(lines[1:]).strip()
    return "", draft.strip()


def letter(draft: str, to: str) -> None:
    subject, body = split_subject(draft)
    body_html = html.escape(body).replace("\n", "<br>")
    to_html = f'<div class="meta">To: {html.escape(to)}</div>' if to else ""
    subj_html = f'<div class="subject">{html.escape(subject)}</div>' if subject else ""
    st.markdown(
        f'<div class="paper">{to_html}{subj_html}{body_html}</div>', unsafe_allow_html=True
    )


def badge(status: str, thread_id: str) -> None:
    kind, label = {
        "awaiting_approval": ("waiting", "Awaiting approval"),
        "sent": ("sent", "Sent"),
    }.get(status, ("bad", status.capitalize()))
    st.markdown(
        f'<span class="badge {kind}">{label}</span>'
        f'<span class="thread">Thread {html.escape(thread_id[:8])}</span>',
        unsafe_allow_html=True,
    )


res = ss.res

# ---------- 1. new email ----------
if res is None:
    with st.form("new"):
        query = st.text_area(
            "What is the email about?", placeholder="medical leave request, simple email"
        )
        c1, c2 = st.columns(2)
        sender = c1.text_input("Your name")
        to_email = c2.text_input("Recipient email")
        recipient = st.text_input("Recipient name (optional)")
        use_dates = st.checkbox("Include dates (e.g. for a leave request)")
        d1, d2 = st.columns(2)
        start = d1.date_input("Start date", dt.date.today())
        end = d2.date_input("End date", dt.date.today())
        go = st.form_submit_button("Generate draft", type="primary")

    if go:
        if not (query.strip() and sender.strip() and to_email.strip()):
            st.warning("Please fill in the topic, your name and the recipient email.")
        else:
            payload = {
                "query": query.strip(),
                "sender_name": sender.strip(),
                "to_email": to_email.strip(),
                "recipient_name": recipient.strip(),
            }
            if use_dates:
                payload["start_date"] = start.isoformat()
                payload["end_date"] = end.isoformat()
            with st.spinner("Writing the draft..."):
                ss.res = call("POST", "/drafts", json=payload)
            if ss.res:
                ss.to = to_email.strip()
                st.rerun()

# ---------- 2. approval / result ----------
else:
    badge(res["status"], res["thread_id"])
    letter(res["draft"], ss.to)
    for issue in res.get("issues", []):
        st.warning(issue)

    if res["status"] == "awaiting_approval":
        if st.button("Approve & Send", type="primary"):
            with st.spinner("Sending..."):
                new = call("POST", f"/drafts/{res['thread_id']}/resume",
                           json={"decision": "approve"})
            if new:
                ss.res = new
                st.rerun()

        st.divider()
        feedback = st.text_input(
            "Want changes? Describe them", placeholder="make it shorter and more formal"
        )
        if st.button("Revise draft"):
            if not feedback.strip():
                st.warning("Please write some feedback first.")
            else:
                with st.spinner("Rewriting..."):
                    new = call("POST", f"/drafts/{res['thread_id']}/resume",
                               json={"decision": "revise", "feedback": feedback.strip()})
                if new:
                    ss.res = new
                    st.rerun()
    elif res["status"] == "sent":
        st.success(res["final_response"])
    else:
        st.error(res["final_response"] or res["status"])
