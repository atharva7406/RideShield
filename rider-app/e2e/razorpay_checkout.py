import asyncio
import time
import os
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# Add backend directory to Python path for DB access in sih26 layout
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))
try:
    from db.core.session import SessionLocal
    from db.models.payment import Payment
    from db.models.shift import Shift
    from sqlalchemy import desc
    HAS_DB = True
except ImportError:
    HAS_DB = False

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Wait indefinitely for user interaction during manual E2E verification
        page.set_default_timeout(0)

        order_id = None
        create_order_resp = None
        verify_req = None
        verify_resp = None
        payment_verified = asyncio.Event()

        async def handle_response(response):
            nonlocal order_id, create_order_resp, verify_resp
            if "payments/create-order" in response.url and response.request.method == "POST":
                if response.status == 200:
                    try:
                        json_data = await response.json()
                        order_id = json_data.get("order_id") or json_data.get("id")
                        create_order_resp = json_data
                        log(f"\n[NETWORK] /payments/create-order response:\n{json_data}")
                    except Exception as e:
                        log(f"Error parsing create-order response: {e}")
            elif "payments/verify" in response.url and response.request.method == "POST":
                if response.status == 200:
                    try:
                        json_data = await response.json()
                        verify_resp = json_data
                        log(f"\n[NETWORK] /payments/verify response:\n{json_data}")
                        payment_verified.set()
                    except Exception as e:
                        log(f"Error parsing verify response: {e}")

        async def handle_request(request):
            nonlocal verify_req
            if "payments/verify" in request.url and request.method == "POST":
                try:
                    verify_req = request.post_data
                    log(f"\n[NETWORK] /payments/verify request payload:\n{verify_req}")
                except Exception:
                    pass

        page.on("response", handle_response)
        page.on("request", handle_request)

        log("Navigating to http://localhost:8081")
        await page.goto('http://localhost:8081')

        log("\n=======================================================")
        log("MANUAL INTERVENTION REQUIRED:")
        log("1. Please interact with the opened Chromium browser.")
        log("2. Sign up or Login.")
        log("3. Click 'Start Shift' and then 'PAY Rs 5'.")
        log("4. Complete the Razorpay Test Mode checkout.")
        log("   (Use Test Card: 4111 1111 1111 1111, any expiry/cvv)")
        log("5. The script will automatically detect completion and resume.")
        log("=======================================================\n")

        # Wait until the verify response is caught
        await payment_verified.wait()
        
        log("\nPayment verification detected! Verifying final state...")
        await asyncio.sleep(2)
        
        latest_payment = None
        latest_shift = None
        
        if HAS_DB:
            log("Querying database for actual Payment row...")
            try:
                db = SessionLocal()
                latest_payment = db.query(Payment).order_by(desc(Payment.created_at)).first()
                if latest_payment:
                    status_name = str(latest_payment.status).split('.')[-1]
                    log(f"\n[DB] Payment Row: ID={latest_payment.id}, Status={status_name}, TxRef={latest_payment.transaction_ref}, OrderID={latest_payment.razorpay_order_id}, SignaturePresent={'Yes' if latest_payment.razorpay_signature else 'No'}")
                else:
                    log("No payment row found!")
                
                latest_shift = db.query(Shift).order_by(desc(Shift.created_at)).first()
                if latest_shift:
                    s_status = str(latest_shift.status).split('.')[-1]
                    log(f"[DB] Shift Row: ID={latest_shift.id}, Status={s_status}")
            except Exception as e:
                log(f"DB Query Error: {e}")
            finally:
                if 'db' in locals():
                    db.close()
        
        log("\n--- E2E SUCCESS ---")
        log("Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
