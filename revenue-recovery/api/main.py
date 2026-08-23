from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.triage import triage_router
from core.triage_scorer.baseline_model import load_baseline_model

app = FastAPI(
    title="Revenue Recovery Agent API",
    description="Autonomous payment recovery agent backend (Razorpay Track 03)",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(triage_router)

@app.on_event("startup")
def startup_event():
    # Warm up baseline model
    load_baseline_model()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
