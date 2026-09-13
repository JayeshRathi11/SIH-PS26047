from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.patients import router as patients_router

app = FastAPI(title="MediKiosk Backend")

# Mount routers
app.include_router(health_router)
app.include_router(patients_router, prefix="/api")
