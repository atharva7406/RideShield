from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, shifts, incidents, claims, telemetry, payments, helmet

app = FastAPI(
    title="RideShield API",
    description="Shift-based microinsurance and risk intelligence backend platform for gig workers.",
    version="1.0.0"
)

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
app.include_router(helmet.router, prefix="/helmet", tags=["Helmet Verification"])

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
