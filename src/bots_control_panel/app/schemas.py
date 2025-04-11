# app/schemas.py
from pydantic import BaseModel, Field
from enum import Enum

# --- Base and Create Schemas ---
class ServiceBase(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_.-]+\.service$", description="Systemd service name (e.g., myapp.service)")

class ServiceCreate(ServiceBase):
    api_key: str = Field(..., min_length=10, description="Unique API key for this service")

# --- Read Schema (used when returning data from DB) ---
class Service(ServiceBase):
    id: int
    # Exclude api_key by default when returning service info for safety
    # If you need to display it (e.g., in an admin panel), create another schema

    class Config:
        # For Pydantic V2: from_attributes replaces orm_mode
        from_attributes = True

# --- API Response Schemas ---
class ServiceResponse(BaseModel):
    service: str
    action: str
    success: bool
    message: str
    details: str | None = None

class ServiceAction(str, Enum):
    """Allowed systemd actions."""
    start = "start"
    stop = "stop"
    restart = "restart"
    status = "status"

# --- API Key Header ---
# We'll handle API key validation manually in the endpoint based on the service
