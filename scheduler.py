"""
Continuous 24/7 scheduler for the email campaign.
Runs scrape + send cycles back-to-back with a short cooldown between cycles.
"""
import asyncio
import logging
import time
import traceback

import sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

# How many queries to scrape per cycle
QUERIES_PER_CYCLE = 20

# Cooldown between cycles (seconds) — prevents hammering Google Maps
CYCLE_COOLDOWN = 300  # 5 minutes


def run_cycle():
    """Run one scrape + send cycle."""
    from india_campaign import load_config, run_full_cycle, send_phase
    from database.db import init_db, sync_gmail_accounts, reset_daily_counts
    from emailer.warmup import advance_warmup
    from emailer.tracker import print_report

    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))
    reset_daily_counts()

    # Run the full scrape + send cycle
    try:
        result = asyncio.run(run_full_cycle(config, max_queries=QUERIES_PER_CYCLE))
        logger.info(f"Cycle result: scraped={result.get('scraped', 0)}, sent={result.get('sent', 0)}")
    except Exception as e:
        logger.error(f"Full cycle error: {e}")
        logger.error(traceback.format_exc())
        # Still try to send any leads we already have
        try:
            logger.info("Attempting fallback send phase with existing leads...")
            sent = send_phase(config)
            logger.info(f"Fallback send phase sent {sent} emails")
        except Exception as se:
            logger.error(f"Fallback send also failed: {se}")

    try:
        advance_warmup()
    except Exception:
        pass

    try:
        print_report()
    except Exception:
        pass


def main():
    logger.info("=" * 60)
    logger.info("  AXENORA AI — CONTINUOUS 24/7 CAMPAIGN")
    logger.info(f"  Queries per cycle: {QUERIES_PER_CYCLE}")
    logger.info(f"  Cooldown between cycles: {CYCLE_COOLDOWN}s")
    logger.info("=" * 60)

    cycle_num = 0
    while True:
        cycle_num += 1
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  STARTING CYCLE #{cycle_num}")
        logger.info(f"{'=' * 60}")

        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle #{cycle_num} failed: {e}")
            logger.error(traceback.format_exc())

        logger.info(f"\nCycle #{cycle_num} complete. Cooling down for {CYCLE_COOLDOWN}s before next cycle...")
        time.sleep(CYCLE_COOLDOWN)


if __name__ == "__main__":
    main()
