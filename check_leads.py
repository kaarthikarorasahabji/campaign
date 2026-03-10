import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from database.db import get_connection, get_email_stats

stats = get_email_stats()
print('=== DB Stats ===')
for k, v in stats.items():
    print(f'  {k}: {v}')

conn = get_connection()
leads = conn.execute(
    "SELECT id, business_name, email, country, has_website FROM leads WHERE email IS NOT NULL AND email != '' LIMIT 50"
).fetchall()
conn.close()

print(f'\nLeads with email ({len(leads)}):')
for l in leads:
    print(f'  {l["id"]:3d} | {l["business_name"][:35]:35s} | {l["email"][:40]:40s} | web={l["has_website"]}')

conn = get_connection()
pending = conn.execute(
    "SELECT COUNT(*) FROM leads l LEFT JOIN emails_sent e ON l.id = e.lead_id WHERE e.id IS NULL AND l.email IS NOT NULL AND l.email != ''"
).fetchone()[0]
conn.close()
print(f'\nPending to send: {pending}')
