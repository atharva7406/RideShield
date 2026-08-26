from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from db.core.session import SessionLocal
from app.api import auth, shifts, incidents, claims, telemetry, payments, whatsapp

def run_db_patches():
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS latitude double precision;"))
        db.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS longitude double precision;"))
        db.execute(text("ALTER TABLE hospitals ALTER COLUMN locality TYPE VARCHAR(500);"))
        db.execute(text("""
            UPDATE hospitals 
            SET latitude = 19.2590, longitude = 72.9858 
            WHERE name ILIKE '%Hiranandani%' OR locality ILIKE '%Thane%';
        """))
        # Patch payment type enum and drop type linkage constraint
        try:
            db.execute(text("ALTER TYPE payment_type_enum ADD VALUE IF NOT EXISTS 'WALLET_RECHARGE';"))
        except Exception as enum_err:
            pass
        try:
            db.execute(text("ALTER TABLE payments DROP CONSTRAINT IF EXISTS ck_payments_type_linkage;"))
        except Exception as const_err:
            pass
        db.commit()
        print("[DB Patch] Successfully checked/patched hospitals columns.")
    except Exception as e:
        print(f"[DB Patch Error]: {e}")
        db.rollback()
    finally:
        db.close()

app = FastAPI(
    title="RideShield API",
    description="Shift-based microinsurance and risk intelligence backend platform for gig workers.",
    version="1.0.0"
)

@app.on_event("startup")
def on_startup():
    run_db_patches()

# Set up CORS origins
origins = [
    "*",  # For hackathon demo allow all
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(shifts.router, prefix="/shifts", tags=["Shifts"])
app.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
app.include_router(claims.router, prefix="/claims", tags=["Claims"])
app.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetry"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp Webhook"])

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "RideShield API",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
