import re
import httpx
from app.core.config import settings

def normalize_phone_e164(phone: str) -> str:
    """
    Normalizes a phone number to E.164 format.
    E.g., "+1 555-010-0000" -> "+15550100000"
    """
    # Remove leading plus and non-digits first
    cleaned = re.sub(r"\D", "", phone)
    
    # If it is 10 digits and starts with Indian prefix, prepend +91
    if len(cleaned) == 10 and cleaned[0] in "6789":
        return "+91" + cleaned
    # If it is 12 digits starting with 91, prepend +
    elif len(cleaned) == 12 and cleaned.startswith("91"):
        return "+" + cleaned
        
    return "+" + cleaned

def is_test_phone_number(phone: str) -> bool:
    """
    Returns True if the normalized phone number is a hackathon bypass test number.
    E.g. numbers starting with '+1555'.
    """
    normalized = normalize_phone_e164(phone)
    return normalized.startswith("+1555")

async def send_whatsapp_message(to_phone: str, body: str, template_params: list = None) -> bool:
    """
    Sends a WhatsApp message using Meta WhatsApp Cloud API.
    If template_params is provided, sends as a template. Otherwise, sends as a free-text response.
    """
    normalized_to = normalize_phone_e164(to_phone)
    # Meta Graph API expects to_phone without leading '+'
    api_recipient = normalized_to.replace("+", "").strip()

    if not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_ACCESS_TOKEN:
        print("=" * 60)
        print(f"[MOCK WHATSAPP MESSAGE] TO: {normalized_to}")
        print(f"BODY: {body}")
        print("=" * 60)
        return True

    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    if template_params:
        # Template message for initial notifications
        payload = {
            "messaging_product": "whatsapp",
            "to": api_recipient,
            "type": "template",
            "template": {
                "name": settings.WHATSAPP_TEMPLATE_NAME,
                "language": {
                    "code": "en_US"
                }
            }
        }
        if settings.WHATSAPP_TEMPLATE_NAME != "hello_world":
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": template_params
                }
            ]
    else:
        # Free-text reply during open 24h customer service window
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": api_recipient,
            "type": "text",
            "text": {"body": body},
        }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if response.status_code in [200, 201]:
                print(f"[WhatsApp Cloud API] Message successfully sent to {normalized_to}")
                return True
            else:
                print(f"[WhatsApp Cloud API ERROR] Status {response.status_code}: {response.text}")
                return False
    except Exception as e:
        print(f"[WhatsApp Cloud API Exception]: {e}")
        return False

async def send_sms_message(to_phone: str, body: str) -> bool:
    """
    Sends an SMS message using Fast2SMS Quick SMS API.
    If FAST2SMS_API_KEY is not set, falls back to printing the message to the console.
    """
    normalized_to = normalize_phone_e164(to_phone)
    # Fast2SMS expects numbers in format "919876543210" or "9876543210" (without '+')
    api_recipient = normalized_to.replace("+", "").strip()

    if not settings.FAST2SMS_API_KEY:
        print("=" * 60)
        print(f"[FREE MOCK SMS] TO: {normalized_to}")
        print(f"BODY: {body}")
        print("=" * 60)
        return True

    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": settings.FAST2SMS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "route": "q",
        "message": body,
        "numbers": api_recipient,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if response.status_code in [200, 201]:
                resp_json = response.json()
                if resp_json.get("return") is True:
                    print(f"[Fast2SMS SMS] Message successfully sent to {normalized_to}")
                    return True
                else:
                    print(f"[Fast2SMS SMS ERROR] API response: {resp_json}")
            else:
                print(f"[Fast2SMS SMS ERROR] Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[Fast2SMS SMS Exception]: {e}")

    # Fallback to console printing so developers can always see the SMS code/text even if API fails
    print("\n" + "=" * 60)
    print(f"[SMS BACKUP FALLBACK] TO: {normalized_to}")
    print(f"BODY: {body}")
    print("=" * 60 + "\n")
    return True

async def make_voice_call(to_phone: str, say_text: str) -> bool:
    """
    Mock Voice Call initiator that prints to console (part of 100% free hackathon architecture).
    """
    normalized = normalize_phone_e164(to_phone)
    print("=" * 60)
    print(f"[FREE MOCK VOICE CALL] TO: {normalized}")
    print(f"SAY: {say_text}")
    print("=" * 60)
    return True
