import logging
from datetime import datetime
from database.db import get_connection, increment_warmup_day

logger = logging.getLogger(__name__)


def advance_warmup():
    """Increment warmup_day for all active accounts at end of day."""
    conn = get_connection()
    accounts = conn.execute("SELECT email, warmup_day, last_sent_date FROM gmail_accounts WHERE active = 1").fetchall()
    conn.close()

    today = datetime.now().strftime("%Y-%m-%d")
    for acc in accounts:
        if acc["last_sent_date"] == today:
            increment_warmup_day(acc["email"])
            logger.info(f"Advanced warmup for {acc['email']} to day {acc['warmup_day'] + 1}")


def get_warmup_status():
    """Return warmup status for all accounts."""
    conn = get_connection()
    accounts = conn.execute(
        "SELECT email, warmup_day, daily_sent, last_sent_date, active FROM gmail_accounts"
    ).fetchall()
    conn.close()
    return [dict(a) for a in accounts]
