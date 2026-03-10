import logging
from database.db import get_email_stats, get_connection

logger = logging.getLogger(__name__)


def print_report():
    """Print a CLI report of email campaign stats."""
    stats = get_email_stats()
    print("\n" + "=" * 55)
    print("       AXENORA AI — CAMPAIGN REPORT")
    print("=" * 55)
    print(f"  Total leads scraped:     {stats['total_leads']}")
    print(f"  Leads with email:        {stats['leads_with_email']}")
    print(f"  Emails sent:             {stats['total_sent']}")
    print(f"  Emails bounced:          {stats['total_bounced']}")
    print(f"  Pending (unsent):        {stats['pending']}")
    print(f"  Queries scraped:         {stats.get('queries_scraped', 0)}")
    print("=" * 55)

    # Per-account breakdown
    conn = get_connection()
    accounts = conn.execute(
        "SELECT email, daily_sent, warmup_day, last_sent_date FROM gmail_accounts WHERE active = 1"
    ).fetchall()
    conn.close()

    if accounts:
        print("\n  Gmail Account Status:")
        print("  " + "-" * 51)
        for acc in accounts:
            print(f"  {acc['email']}: sent today={acc['daily_sent']}, warmup day={acc['warmup_day']}")
    print()


def get_sent_today():
    conn = get_connection()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM emails_sent WHERE date(sent_at) = ?", (today,)
    ).fetchone()[0]
    conn.close()
    return count
