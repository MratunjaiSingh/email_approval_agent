import os
from dotenv import load_dotenv
from .mailer import DryRunMailer, SMTPMailer

load_dotenv()


def get_llm():
    from langchain.chat_models import init_chat_model

    model = os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("Set LLM_MODEL in .env (e.g. groq:openai/gpt-oss-120b)")
    return init_chat_model(model, temperature=0.3)


def get_mailer():
    dry = os.getenv("DRY_RUN", "true").lower() == "true"
    user, pwd = os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", "")
    if dry or not (user and pwd):
        return DryRunMailer()
    return SMTPMailer(
        os.getenv("SMTP_HOST", "smtp.gmail.com"),
        int(os.getenv("SMTP_PORT", "587")),
        user,
        pwd,
    )


def checkpoint_db() -> str:
    return os.getenv("CHECKPOINT_DB", "checkpoints.db")
