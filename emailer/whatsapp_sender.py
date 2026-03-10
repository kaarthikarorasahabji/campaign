"""
WhatsApp sender — Python wrapper around whatsapp-web.js Node.js module.
Sends WhatsApp messages by calling the Node.js send.js script via subprocess.
"""
import subprocess
import json
import os
import logging
import yaml
import random

logger = logging.getLogger(__name__)

WHATSAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "whatsapp")
TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "whatsapp_templates.yaml")


def load_whatsapp_templates():
    """Load WhatsApp message templates from YAML."""
    if os.path.exists(TEMPLATES_PATH):
        with open(TEMPLATES_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def format_phone_for_whatsapp(phone, country="India"):
    """
    Format a phone number for WhatsApp (international format, no +).
    India: adds 91 prefix if not already present.
    """
    if not phone:
        return None

    # Remove all non-digit characters
    digits = "".join(c for c in phone if c.isdigit())

    if not digits or len(digits) < 7:
        return None

    # For India, add 91 prefix
    if country and country.lower() == "india":
        if digits.startswith("91") and len(digits) >= 12:
            return digits
        elif digits.startswith("0"):
            return "91" + digits[1:]
        elif len(digits) == 10:
            return "91" + digits

    # For other countries, assume the number includes country code
    return digits


def send_whatsapp_message(phone, message, timeout=90):
    """
    Send a WhatsApp message using the Node.js sender.

    Args:
        phone: Phone number in any format (will be cleaned)
        message: Text message to send
        timeout: Max seconds to wait for the Node process

    Returns:
        dict: {"success": True/False, "error": "..." if failed}
    """
    send_script = os.path.join(WHATSAPP_DIR, "send.js")

    if not os.path.exists(send_script):
        return {"success": False, "error": "whatsapp/send.js not found"}

    # Check if session exists
    session_dir = os.path.join(WHATSAPP_DIR, "session")
    if not os.path.exists(session_dir):
        return {"success": False, "error": "WhatsApp session not found. Run 'node auth.js' first."}

    try:
        result = subprocess.run(
            ["node", send_script, phone, message],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=WHATSAPP_DIR,
        )

        # Parse JSON output
        output = result.stdout.strip()
        if output:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"success": False, "error": f"Invalid output: {output[:200]}"}

        return {"success": False, "error": result.stderr[:200] if result.stderr else "No output"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "WhatsApp send timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "Node.js not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_cold_whatsapp(lead, config):
    """
    Send a cold WhatsApp message to a lead using a random template.

    Args:
        lead: dict with business_name, phone, category, location, country
        config: campaign config dict

    Returns:
        dict: {"success": True/False, "error": "..."}
    """
    phone = lead.get("phone")
    country = lead.get("country", "India")

    if not phone:
        return {"success": False, "error": "No phone number"}

    formatted_phone = format_phone_for_whatsapp(phone, country)
    if not formatted_phone:
        return {"success": False, "error": f"Invalid phone: {phone}"}

    # Load templates
    templates = load_whatsapp_templates()
    if not templates:
        return {"success": False, "error": "No WhatsApp templates found"}

    # Pick a random template (not followup)
    template_keys = [k for k in templates.keys() if k != "followup" and isinstance(templates[k], str)]
    if not template_keys:
        return {"success": False, "error": "No valid templates"}

    template_key = random.choice(template_keys)
    template_text = templates[template_key]

    # Get sender info
    sender = config.get("sender", {})

    # Format the message
    city = lead.get("location") or "your area"
    if "," in city:
        city = city.split(",")[0].strip()

    message = template_text.format(
        business_name=lead.get("business_name", ""),
        category=lead.get("category", "business"),
        city=city,
        sender_name=sender.get("name", ""),
        sender_phone=sender.get("phone", ""),
        calendar_link=sender.get("calendar_link", ""),
    )

    logger.info(f"  📲 Sending WhatsApp to {formatted_phone} ({lead.get('business_name')})")

    result = send_whatsapp_message(formatted_phone, message)

    if result.get("success"):
        logger.info(f"  ✅ WhatsApp sent to {formatted_phone}")
    else:
        logger.warning(f"  ❌ WhatsApp failed for {formatted_phone}: {result.get('error')}")

    return result
