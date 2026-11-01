"""Dates and weekdays are computed in code, never by the LLM (avoids hallucinations)."""
from datetime import date, timedelta


def parse_iso(s: str) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def fmt_date(d: date) -> str:
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"


def date_facts(start: str, end: str) -> str:
    s, e = parse_iso(start), parse_iso(end)
    if s and e:
        days = (e - s).days + 1
        return (
            f"Start date: {fmt_date(s)}\n"
            f"End date: {fmt_date(e)}\n"
            f"Duration: {days} day{'s' if days != 1 else ''}"
        )
    if s:
        return f"Date: {fmt_date(s)}"
    return ""


def allowed_weekdays(start: str, end: str) -> set[str]:
    s, e = parse_iso(start), parse_iso(end)
    if not s:
        return set()
    e = e or s
    names: set[str] = set()
    d = s
    while d <= e and len(names) < 7:
        names.add(d.strftime("%A"))
        d += timedelta(days=1)
    return names
