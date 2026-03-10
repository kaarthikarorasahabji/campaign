"""
Hugging Face Spaces entry point.
Runs the campaign scheduler in a background thread,
and a simple health-check HTTP server on port 7860
to keep the Space alive.
"""
import threading
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

# Track campaign status for the health page
campaign_status = {"last_cycle": "starting...", "cycles": 0, "started_at": datetime.now().isoformat()}


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal health endpoint to keep HF Space alive."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = f"""<!DOCTYPE html>
        <html><head><title>Axenora AI Campaign</title>
        <meta http-equiv="refresh" content="60">
        <style>
            body {{ font-family: monospace; background: #0a0a0a; color: #00ff88; padding: 40px; }}
            h1 {{ color: #fff; }}
            .status {{ background: #111; padding: 20px; border-radius: 8px; margin: 10px 0; }}
        </style></head>
        <body>
            <h1>🚀 Axenora AI — Campaign Engine</h1>
            <div class="status">
                <p>⏱ Started: {campaign_status['started_at']}</p>
                <p>🔄 Cycles completed: {campaign_status['cycles']}</p>
                <p>📊 Last cycle: {campaign_status['last_cycle']}</p>
                <p>✅ Status: RUNNING</p>
            </div>
            <p style="color:#666">Auto-refreshes every 60s</p>
        </body></html>"""
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP access logs


def run_health_server():
    """Run the health HTTP server on port 7860."""
    server = HTTPServer(("0.0.0.0", 7860), HealthHandler)
    logger.info("Health server running on port 7860")
    server.serve_forever()


def run_campaign():
    """Run the campaign scheduler (blocking)."""
    import time
    import traceback

    QUERIES_PER_CYCLE = 20
    CYCLE_COOLDOWN = 300  # 5 minutes

    from india_campaign import load_config, run_full_cycle, send_phase
    from database.db import init_db, sync_gmail_accounts, reset_daily_counts
    from emailer.warmup import advance_warmup
    from emailer.tracker import print_report
    import asyncio

    while True:
        campaign_status["cycles"] += 1
        cycle_num = campaign_status["cycles"]
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  STARTING CYCLE #{cycle_num}")
        logger.info(f"{'=' * 60}")

        try:
            config = load_config()
            init_db()
            sync_gmail_accounts(config.get("gmail_accounts", []))
            reset_daily_counts()

            result = asyncio.run(run_full_cycle(config, max_queries=QUERIES_PER_CYCLE))
            campaign_status["last_cycle"] = f"Cycle #{cycle_num}: scraped={result.get('scraped', 0)}, sent={result.get('sent', 0)}"
            logger.info(f"Cycle #{cycle_num} result: {result}")
        except Exception as e:
            logger.error(f"Cycle #{cycle_num} failed: {e}")
            logger.error(traceback.format_exc())
            campaign_status["last_cycle"] = f"Cycle #{cycle_num}: ERROR - {e}"
            # Still try to send
            try:
                config = load_config()
                sent = send_phase(config)
                logger.info(f"Fallback send: {sent} emails")
            except Exception:
                pass

        try:
            advance_warmup()
        except Exception:
            pass
        try:
            print_report()
        except Exception:
            pass

        logger.info(f"Cycle #{cycle_num} complete. Cooling down for {CYCLE_COOLDOWN}s...")
        time.sleep(CYCLE_COOLDOWN)


def main():
    logger.info("=" * 60)
    logger.info("  AXENORA AI — Hugging Face Spaces Deployment")
    logger.info("  Gmail SMTP + Resend | 24/7 Campaign Engine")
    logger.info("=" * 60)

    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Run campaign in main thread (blocking)
    run_campaign()


if __name__ == "__main__":
    main()
