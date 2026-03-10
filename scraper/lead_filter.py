import re
import logging
import dns.resolver

logger = logging.getLogger(__name__)


def is_valid_email_format(email):
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def check_mx_record(email):
    """Verify the email domain has valid MX records."""
    if not email:
        return False
    domain = email.split("@")[-1]
    try:
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


def validate_email(email):
    return is_valid_email_format(email) and check_mx_record(email)


def filter_leads(leads):
    """
    Filter scraped leads:
    - Keep only those WITHOUT websites (or broken ones)
    - Deduplicate by phone/email
    - Validate email addresses
    """
    seen_phones = set()
    seen_emails = set()
    filtered = []

    for lead in leads:
        # Skip businesses with websites
        if lead.get("has_website"):
            continue

        phone = lead.get("phone", "").strip()
        email = lead.get("email", "").strip().lower()

        # Deduplicate
        if phone and phone in seen_phones:
            continue
        if email and email in seen_emails:
            continue

        # Validate email if present
        if email and not is_valid_email_format(email):
            lead["email"] = None
            email = ""

        if phone:
            seen_phones.add(phone)
        if email:
            seen_emails.add(email)

        filtered.append(lead)

    logger.info(f"Filtered {len(leads)} leads down to {len(filtered)}")
    return filtered


def validate_lead_emails(leads):
    """Validate emails with MX check (slower, use selectively)."""
    valid = []
    for lead in leads:
        email = lead.get("email", "")
        if email and validate_email(email):
            valid.append(lead)
        elif not email:
            valid.append(lead)  # Keep leads without email (might find later)
        else:
            logger.info(f"Invalid email dropped: {email}")
    return valid
