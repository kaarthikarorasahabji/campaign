"""Send emails via Resend API for international leads."""
import resend
import random
import time
import logging
from jinja2 import Template
from database.db import record_email_sent

logger = logging.getLogger(__name__)


def send_via_resend(to_email, subject, html_body, resend_config):
    """Send a single email via Resend API."""
    resend.api_key = resend_config["api_key"]

    try:
        params = {
            "from": f"{resend_config.get('from_name', 'Axenora AI')} <{resend_config['from_email']}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        r = resend.Emails.send(params)
        email_id = r.get("id", "ok") if isinstance(r, dict) else str(r)
        logger.info(f"Resend sent to {to_email} (id: {email_id})")
        return True
    except Exception as e:
        logger.error(f"Resend failed for {to_email}: {e}")
        return False


def send_to_lead_resend(lead, template_html, resend_config, sender_info, min_delay=15, max_delay=60):
    """Send a personalized email to an international lead via Resend."""
    template = Template(template_html)

    city = lead["location"] or "your area"
    if "," in city:
        city = city.split(",")[0].strip()

    html_body = template.render(
        business_name=lead["business_name"],
        category=lead["category"] or "your business",
        city=city,
        sender_name=sender_info.get("name", ""),
        sender_company=sender_info.get("company", ""),
        sender_phone=sender_info.get("phone", ""),
        sender_website=sender_info.get("website", ""),
        calendar_link=sender_info.get("calendar_link", ""),
    )

    subject_templates = [
        f"Never miss a customer call again, {lead['business_name']}",
        f"{lead['business_name']} — your AI receptionist is ready",
        f"Stop missing calls at {lead['business_name']}",
    ]
    subject = random.choice(subject_templates)

    success = send_via_resend(lead["email"], subject, html_body, resend_config)
    status = "sent" if success else "bounced"
    record_email_sent(lead["id"], resend_config["from_email"], "international_cold", status)

    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return success
