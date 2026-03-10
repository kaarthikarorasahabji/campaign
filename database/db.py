import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "leads.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            category TEXT,
            phone TEXT,
            email TEXT,
            location TEXT,
            country TEXT,
            has_website INTEGER DEFAULT 0,
            website_url TEXT,
            scraped_at TEXT DEFAULT (datetime('now')),
            UNIQUE(phone, email, business_name)
        );

        CREATE TABLE IF NOT EXISTS emails_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            gmail_account TEXT NOT NULL,
            sent_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'sent',
            template_used TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );

        CREATE TABLE IF NOT EXISTS gmail_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            app_password TEXT NOT NULL,
            daily_sent INTEGER DEFAULT 0,
            warmup_day INTEGER DEFAULT 1,
            last_sent_date TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS scraped_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL UNIQUE,
            city TEXT,
            country TEXT,
            scraped_at TEXT DEFAULT (datetime('now')),
            results_count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
        CREATE INDEX IF NOT EXISTS idx_leads_has_website ON leads(has_website);
        CREATE INDEX IF NOT EXISTS idx_emails_sent_lead ON emails_sent(lead_id);
        CREATE INDEX IF NOT EXISTS idx_emails_sent_status ON emails_sent(status);
        CREATE INDEX IF NOT EXISTS idx_scraped_queries_query ON scraped_queries(query);
    """)
    conn.commit()
    conn.close()


def insert_lead(business_name, category, phone, email, location, country, has_website, website_url=None):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO leads
               (business_name, category, phone, email, location, country, has_website, website_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (business_name, category, phone, email, location, country, int(has_website), website_url),
        )
        conn.commit()
    finally:
        conn.close()


def get_unsent_leads(limit=50):
    """Get leads that have email addresses and have NOT been emailed yet."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT l.* FROM leads l
           LEFT JOIN emails_sent e ON l.id = e.lead_id
           WHERE e.id IS NULL AND l.email IS NOT NULL AND l.email != ''
           ORDER BY l.scraped_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def get_total_unsent_count():
    """Get total count of unsent leads with emails."""
    conn = get_connection()
    count = conn.execute(
        """SELECT COUNT(*) FROM leads l
           LEFT JOIN emails_sent e ON l.id = e.lead_id
           WHERE e.id IS NULL AND l.email IS NOT NULL AND l.email != ''"""
    ).fetchone()[0]
    conn.close()
    return count


def record_email_sent(lead_id, gmail_account, template_used, status="sent"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO emails_sent (lead_id, gmail_account, template_used, status) VALUES (?, ?, ?, ?)",
        (lead_id, gmail_account, template_used, status),
    )
    conn.commit()
    conn.close()


def sync_gmail_accounts(accounts):
    """Sync Gmail accounts from config into the database."""
    conn = get_connection()
    for acc in accounts:
        conn.execute(
            """INSERT INTO gmail_accounts (email, app_password, active)
               VALUES (?, ?, ?)
               ON CONFLICT(email) DO UPDATE SET app_password=excluded.app_password, active=excluded.active""",
            (acc["email"], acc["app_password"], int(acc.get("active", True))),
        )
    conn.commit()
    conn.close()


def get_active_gmail_accounts():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM gmail_accounts WHERE active = 1").fetchall()
    conn.close()
    return rows


def reset_daily_counts():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "UPDATE gmail_accounts SET daily_sent = 0 WHERE last_sent_date != ? OR last_sent_date IS NULL",
        (today,),
    )
    conn.commit()
    conn.close()


def increment_sent_count(email):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "UPDATE gmail_accounts SET daily_sent = daily_sent + 1, last_sent_date = ? WHERE email = ?",
        (today, email),
    )
    conn.commit()
    conn.close()


def increment_warmup_day(email):
    conn = get_connection()
    conn.execute("UPDATE gmail_accounts SET warmup_day = warmup_day + 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def mark_query_scraped(query, city, country, results_count):
    """Record a query as scraped."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO scraped_queries
               (query, city, country, results_count)
               VALUES (?, ?, ?, ?)""",
            (query, city, country, results_count),
        )
        conn.commit()
    finally:
        conn.close()


def is_query_scraped(query):
    """Check if a query has already been scraped."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM scraped_queries WHERE query = ?", (query,)
    ).fetchone()
    conn.close()
    return row is not None


def get_email_stats():
    conn = get_connection()
    stats = {}
    stats["total_leads"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats["leads_with_email"] = conn.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    stats["total_sent"] = conn.execute("SELECT COUNT(*) FROM emails_sent WHERE status = 'sent'").fetchone()[0]
    stats["total_bounced"] = conn.execute("SELECT COUNT(*) FROM emails_sent WHERE status = 'bounced'").fetchone()[0]
    stats["pending"] = conn.execute(
        """SELECT COUNT(*) FROM leads l
           LEFT JOIN emails_sent e ON l.id = e.lead_id
           WHERE e.id IS NULL AND l.email IS NOT NULL AND l.email != ''"""
    ).fetchone()[0]
    try:
        stats["queries_scraped"] = conn.execute("SELECT COUNT(*) FROM scraped_queries").fetchone()[0]
    except Exception:
        stats["queries_scraped"] = 0
    conn.close()
    return stats


if __name__ == "__main__":
    init_db()
    print("Database initialized.")

