from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import TokenResponse, build_token_response
from app.config import get_settings
from app.routers import browse, collector, health, machines, tags

settings = get_settings()

app = FastAPI(title="OPC Platform API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    return build_token_response(form_data, settings)


app.include_router(machines.router)
app.include_router(tags.router)
app.include_router(browse.router)
app.include_router(collector.router)
app.include_router(health.router)
