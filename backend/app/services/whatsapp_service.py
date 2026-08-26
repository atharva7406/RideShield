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

    # 0. Hackathon mock bypass for test numbers (e.g. +1555...)
    if is_test_phone_number(normalized_to):
        print("=" * 60)
        print(f"[MOCK TWILIO/META BYPASS] Test phone number detected: {normalized_to}")
        print(f"BODY: {body}")
        print("=" * 60)
        return True

    # 1. Attempt Twilio WhatsApp sending if credentials are provided
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER:
        twilio_recipient = f"whatsapp:{normalized_to}"
        twilio_sender = settings.TWILIO_FROM_NUMBER
        if not twilio_sender.startswith("whatsapp:"):
            twilio_sender = f"whatsapp:{twilio_sender}"
            
        twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        twilio_data = {
            "To": twilio_recipient,
            "From": twilio_sender,
            "Body": body,
        }
        
        # Check if using the official Twilio Sandbox number to automatically format template-compliant messages
        if "14155238886" in twilio_sender:
            # Twilio Sandbox pre-approved template format: "Your {1} code is {2}"
            if "YES" in body or "HELP" in body:
                sandbox_body = "Your RideShield safety verification code is YES (if safe) or HELP (for SOS)"
            elif "Ride Safe" in body:
                sandbox_body = "Your RideShield status code is SAFE"
            elif "Emergency" in body:
                sandbox_body = "Your RideShield status code is EMERGENCY"
            else:
                sandbox_body = f"Your RideShield status code is {body[:30]}"
            
            print(f"[Twilio Sandbox Optimization] Re-formatted body to match sandbox template: '{sandbox_body}'")
            twilio_data["Body"] = sandbox_body
        try:
            print(f"[Twilio WhatsApp] Attempting to send message to {normalized_to} from {twilio_sender}...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    twilio_url,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                    data=twilio_data,
                    timeout=10.0
                )
                if response.status_code in [200, 201]:
                    print(f"[Twilio WhatsApp] Message successfully sent to {normalized_to}")
                    return True
                else:
                    print(f"[Twilio WhatsApp ERROR] Status {response.status_code}: {response.text}")
                    print("[Twilio WhatsApp] Falling back to Meta WhatsApp Cloud API...")
        except Exception as e:
            print(f"[Twilio WhatsApp Exception]: {e}")
            print("[Twilio WhatsApp] Falling back to Meta WhatsApp Cloud API...")

    # 2. Fallback to Meta WhatsApp Cloud API
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

async def send_twilio_sms(to_phone: str, body: str) -> bool:
    """
    Sends a standard SMS using Twilio.
    """
    normalized_to = normalize_phone_e164(to_phone)
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        print("\n" + "=" * 60)
        print(f"[MOCK TWILIO SMS] TO: {normalized_to}")
        print(f"BODY: {body}")
        print("=" * 60 + "\n")
        return True
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    
    # Twilio SMS sender number (usually a regular phone number, if TWILIO_FROM_NUMBER is whatsapp, we clean it)
    from_number = settings.TWILIO_FROM_NUMBER
    if from_number.startswith("whatsapp:"):
        from_number = from_number.replace("whatsapp:", "")
        
    data = {
        "To": normalized_to,
        "From": from_number,
        "Body": body,
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data=data,
                timeout=10.0
            )
            if response.status_code in [200, 201]:
                print(f"[Twilio SMS] Emergency SMS successfully sent to {normalized_to}")
                return True
            else:
                print(f"[Twilio SMS ERROR] Status {response.status_code}: {response.text}")
                return False
    except Exception as e:
        print(f"[Twilio SMS Exception]: {e}")
        return False

async def send_emergency_sms(rider_id, incident_id, lat: float, lng: float, db) -> bool:
    """
    Looks up the rider's emergency contact phone and sends a standard SMS with a live Google Maps location link.
    """
    from db.models.user import User
    # Get rider
    rider = db.query(User).filter(User.id == rider_id).first()
    if not rider:
        print(f"[Emergency SMS ERROR] Rider {rider_id} not found.")
        return False
    
    profile = rider.rider_profile
    if not profile or not profile.emergency_contact_phone:
        print(f"[Emergency SMS Warning] No emergency contact phone set for {rider.full_name}.")
        return False
        
    phone = profile.emergency_contact_phone
    body = (
        f"RideShield EMERGENCY ALERT: Your emergency contact {rider.full_name} has triggered an SOS! "
        f"Live location: https://maps.google.com/?q={lat},{lng}"
    )
    
    return await send_twilio_sms(phone, body)
