import urllib.parse
import requests
from app.core.config import settings

def is_twilio_configured() -> bool:
    return bool(
        settings.TWILIO_ACCOUNT_SID and 
        settings.TWILIO_AUTH_TOKEN and 
        settings.TWILIO_PHONE_NUMBER
    )

async def send_sms_message(to_phone: str, body: str) -> bool:
    """
    Sends an SMS message using Twilio SMS API.
    If Twilio is not configured, logs the message and returns True.
    """
    if not is_twilio_configured():
        print("="*60)
        print(f"[MOCK TWILIO SMS] TO: {to_phone}")
        print(f"BODY: {body}")
        print("="*60)
        return True

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "To": to_phone,
        "From": settings.TWILIO_PHONE_NUMBER,
        "Body": body
    }
    try:
        response = requests.post(url, data=data, auth=auth, timeout=10)
        if response.status_code in [200, 201]:
            print(f"[Twilio SMS] Message sent to {to_phone}")
            return True
        else:
            print(f"[Twilio SMS ERROR] Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[Twilio SMS Exception]: {e}")
        return False

async def send_whatsapp_message(to_phone: str, body: str) -> bool:
    """
    Sends a WhatsApp message using Twilio WhatsApp API.
    If Twilio is not configured, logs the message and returns True.
    """
    whatsapp_from = settings.TWILIO_WHATSAPP_NUMBER or "whatsapp:+14155238886" # default Twilio sandbox number
    if not whatsapp_from.startswith("whatsapp:"):
        whatsapp_from = f"whatsapp:{whatsapp_from}"
        
    formatted_to = to_phone
    if not formatted_to.startswith("whatsapp:"):
        formatted_to = f"whatsapp:{formatted_to}"

    if not is_twilio_configured():
        print("="*60)
        print(f"[MOCK TWILIO WHATSAPP] TO: {formatted_to}")
        print(f"FROM: {whatsapp_from}")
        print(f"BODY: {body}")
        print("="*60)
        return True

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "To": formatted_to,
        "From": whatsapp_from,
        "Body": body
    }
    try:
        response = requests.post(url, data=data, auth=auth, timeout=10)
        if response.status_code in [200, 201]:
            print(f"[Twilio WhatsApp] Message sent to {formatted_to}")
            return True
        else:
            print(f"[Twilio WhatsApp ERROR] Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[Twilio WhatsApp Exception]: {e}")
        return False

async def make_voice_call(to_phone: str, say_text: str) -> bool:
    """
    Triggers an outbound Voice Call using Twilio Voice API speaking the say_text.
    If Twilio is not configured, logs the call details.
    """
    if not is_twilio_configured():
        print("="*60)
        print(f"[MOCK TWILIO VOICE CALL] TO: {to_phone}")
        print(f"SAY: {say_text}")
        print("="*60)
        return True

    # Use public twimlets to generate a voice message response
    encoded_text = urllib.parse.quote_plus(say_text)
    twimlet_url = f"http://twimlets.com/message?Message%5B0%5D={encoded_text}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls.json"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "To": to_phone,
        "From": settings.TWILIO_PHONE_NUMBER,
        "Url": twimlet_url
    }
    try:
        response = requests.post(url, data=data, auth=auth, timeout=10)
        if response.status_code in [200, 201]:
            print(f"[Twilio Voice Call] Initiated call to {to_phone}")
            return True
        else:
            print(f"[Twilio Voice Call ERROR] Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[Twilio Voice Call Exception]: {e}")
        return False
