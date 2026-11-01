"""Guardrails: decide whether a draft is safe to send."""
import re
from .dates import allowed_weekdays

PLACEHOLDER_RE = re.compile(r"\[[^\]\n]{1,60}\]")
WEEKDAY_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I
)


def split_subject(draft: str) -> tuple[str, str]:
    lines = draft.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
        return subject, body
    return "(no subject)", draft.strip()


def validate_draft(
    draft: str, sender_name: str = "", start_date: str = "", end_date: str = ""
) -> list[str]:
    if not draft.strip():
        return ["Draft is empty."]

    issues: list[str] = []

    if not draft.lstrip().lower().startswith("subject:"):
        issues.append("First line must be 'Subject: <subject>'.")

    placeholders = sorted(set(PLACEHOLDER_RE.findall(draft)))
    if placeholders:
        issues.append(f"Remove placeholders: {', '.join(placeholders)}.")

    if sender_name and sender_name.lower() not in draft.lower():
        issues.append(f"Sign off with the sender name '{sender_name}'.")

    allowed = allowed_weekdays(start_date, end_date)
    if allowed:
        found = {m.capitalize() for m in WEEKDAY_RE.findall(draft)}
        wrong = found - allowed
        if wrong:
            issues.append(
                f"Wrong weekday(s): {', '.join(sorted(wrong))}. "
                f"Valid for the given dates: {', '.join(sorted(allowed))}."
            )

    return issues
