from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import models

from database import lifespan
from routes.ai_routes import router as ai_router
from routes.admin_routes import router as admin_router
from routes.auth_routes import router as auth_router
from routes.dashboard_routes import router as dashboard_router
from routes.favorite_routes import router as favorite_router
from routes.media_routes import router as media_router
from routes.menu_import_routes import router as menu_import_router
from routes.menu_image_routes import router as menu_image_router
from routes.engagement_routes import router as engagement_router
from routes.place_routes import router as place_router
from routes.provider_routes import router as provider_router


app = FastAPI(
    title="AskMyCity API",
    description=(
        "Backend API for local businesses, "
        "accounts, authentication, and AI search."
    ),
    version="7.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



MEDIA_ROOT = Path(__file__).resolve().parent / "uploads"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(favorite_router)
app.include_router(media_router)
app.include_router(menu_import_router)
app.include_router(menu_image_router)
app.include_router(engagement_router)
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(place_router)
app.include_router(provider_router)


@app.get("/", tags=["Home"])
def home():
    return {
        "message": (
            "AskMyCity API version 7 "
            "is connected to PostgreSQL."
        )
    }