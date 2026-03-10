"""
Lightweight scheduler for Railway free tier.
Runs one cycle per day, then sleeps — uses minimal compute hours.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def already_ran_today():
    """Check if we already sent emails today."""
    import sqlite3
    from database.db import get_connection
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM emails_sent WHERE date(sent_at) = ?", (today,)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        count = 0
    conn.close()
    return count > 0


def run_daily_cycle():
    """Run one scrape + send cycle."""
    from india_campaign import load_config, run_full_cycle, send_phase
    from database.db import init_db, sync_gmail_accounts, reset_daily_counts
    from emailer.warmup import advance_warmup
    from emailer.tracker import print_report

    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))
    reset_daily_counts()

    # Run the full cycle with limited queries to save compute
    asyncio.run(run_full_cycle(config, max_queries=10))

    advance_warmup()
    print_report()


def seconds_until_9am():
    """Calculate seconds until next 9 AM IST."""
    try:
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
    except ImportError:
        # Fallback: assume server is in IST
        now = datetime.now()

    tomorrow_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now.hour >= 9:
        tomorrow_9am += timedelta(days=1)

    diff = (tomorrow_9am - now).total_seconds()
    return max(diff, 60)  # At least 60 seconds


def main():
    logger.info("=" * 50)
    logger.info("  AXENORA AI — Railway Free Tier Scheduler")
    logger.info("  Mode: 1 cycle/day, 50 emails max")
    logger.info("=" * 50)

    while True:
        if already_ran_today():
            wait = seconds_until_9am()
            hours = wait / 3600
            logger.info(f"Already ran today. Sleeping {hours:.1f} hours until next 9 AM...")
            time.sleep(wait)
            continue

        logger.info("Starting daily cycle...")
        try:
            run_daily_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")

        # Sleep until tomorrow 9 AM
        wait = seconds_until_9am()
        hours = wait / 3600
        logger.info(f"Cycle complete. Sleeping {hours:.1f} hours until next run...")
        time.sleep(wait)


if __name__ == "__main__":
    main()
