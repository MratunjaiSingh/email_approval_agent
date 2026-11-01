from app.dates import allowed_weekdays, date_facts
from app.validators import split_subject, validate_draft

GOOD = "Subject: Leave\n\nDear Sir,\nLeave from Monday, 2 November 2026 to Friday, 6 November 2026.\n\nRegards,\nMratunjai"


def test_weekdays_computed_correctly():
    facts = date_facts("2026-11-02", "2026-11-06")
    assert "Monday, 2 November 2026" in facts
    assert "Friday, 6 November 2026" in facts
    assert "5 days" in facts


def test_allowed_weekdays():
    assert allowed_weekdays("2026-11-02", "2026-11-04") == {"Monday", "Tuesday", "Wednesday"}


def test_good_draft_passes():
    assert validate_draft(GOOD, "Mratunjai", "2026-11-02", "2026-11-06") == []


def test_placeholder_detected():
    bad = GOOD.replace("Dear Sir", "Dear [Supervisor's Name]")
    assert any("placeholder" in i.lower() for i in validate_draft(bad, "Mratunjai"))


def test_wrong_weekday_detected():
    bad = GOOD.replace("Monday", "Sunday")
    assert any("weekday" in i.lower() for i in validate_draft(bad, "Mratunjai", "2026-11-02", "2026-11-06"))


def test_missing_subject_and_sender():
    issues = validate_draft("Hello there", "Mratunjai")
    assert len(issues) == 2


def test_split_subject():
    assert split_subject("Subject: Hi\n\nBody") == ("Hi", "Body")


def test_single_day_duration_is_singular():
    assert "Duration: 1 day" in date_facts("2026-11-01", "2026-11-01")
    assert "1 days" not in date_facts("2026-11-01", "2026-11-01")
