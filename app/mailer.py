import logging
import smtplib
import time
from email.message import EmailMessage

log = logging.getLogger(__name__)


class DryRunMailer:
    """Logs the email instead of sending it (for development and testing)."""

    def __call__(self, to: str, subject: str, body: str) -> None:
        log.info("[DRY RUN] to=%s subject=%s\n%s", to, subject, body)
        print(f"[DRY RUN] email to={to!r} subject={subject!r}")


class SMTPMailer:
    def __init__(self, host: str, port: int, user: str, password: str, retries: int = 3):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.retries = retries

    def __call__(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        for attempt in range(1, self.retries + 1):
            try:
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    smtp.starttls()
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
                return
            except (smtplib.SMTPException, OSError):
                log.exception("SMTP attempt %d/%d failed", attempt, self.retries)
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)
