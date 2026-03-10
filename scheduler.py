"""
Server-mode scheduler for India-scale email campaign.
Runs on Railway (or any server) as a long-running process.
Executes scrape+send cycles on a daily schedule.
"""
import asyncio
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from india_campaign import load_config, run_full_cycle, send_phase, scrape_phase
from database.db import init_db, sync_gmail_accounts, reset_daily_counts
from emailer.warmup import advance_warmup
from emailer.tracker import print_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def init():
    """Initialize DB and sync accounts."""
    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))
    return config


def morning_cycle():
    """9 AM: Full scrape + send cycle (50 queries per run)."""
    logger.info("=== MORNING CYCLE: Scrape + Send ===")
    config = init()
    reset_daily_counts()
    asyncio.run(run_full_cycle(config, max_queries=50))


def midday_send():
    """1 PM: Send-only pass to hit daily targets."""
    logger.info("=== MIDDAY SEND ===")
    config = init()
    sent = send_phase(config)
    logger.info(f"Midday send: {sent} emails sent")
    print_report()


def afternoon_scrape():
    """4 PM: Extra scrape run to build up the lead pipeline."""
    logger.info("=== AFTERNOON SCRAPE ===")
    config = init()
    asyncio.run(scrape_phase(config, max_queries=30))
    print_report()


def end_of_day():
    """7 PM: Advance warmup + daily report."""
    logger.info("=== END OF DAY ===")
    advance_warmup()
    print_report()


def start_scheduler():
    """Start the APScheduler with IST-timed jobs."""
    # Run init once at startup
    config = init()
    logger.info("Server started. Running initial cycle...")

    # Run one cycle immediately on startup
    reset_daily_counts()
    try:
        asyncio.run(run_full_cycle(config, max_queries=30))
    except Exception as e:
        logger.error(f"Initial cycle failed: {e}")

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    # Morning: full cycle
    scheduler.add_job(morning_cycle, "cron", hour=9, minute=0, id="morning_cycle")

    # Midday: send only
    scheduler.add_job(midday_send, "cron", hour=13, minute=0, id="midday_send")

    # Afternoon: extra scrape
    scheduler.add_job(afternoon_scrape, "cron", hour=16, minute=0, id="afternoon_scrape")

    # End of day: warmup + report
    scheduler.add_job(end_of_day, "cron", hour=19, minute=0, id="end_of_day")

    logger.info("\nScheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  {job.id}: {job.trigger}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
