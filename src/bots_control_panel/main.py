import os
import subprocess
from enum import Enum
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from dotenv import load_dotenv # Optional, for local .env file loading

# Load environment variables (especially for local dev)
load_dotenv()

# --- Configuration ---
# Explicitly allow only this service
ALLOWED_SERVICE_NAME = "armello_bot.service"
# Get API key from environment variable for security
EXPECTED_API_KEY = os.getenv("EXPECTED_API_KEY")
if not EXPECTED_API_KEY:
    raise ValueError("FATAL: EXPECTED_API_KEY environment variable not set.")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Define allowed actions using Enum for validation
class ServiceAction(str, Enum):
    start = "start"
    stop = "stop"
    restart = "restart"
    status = "status" # Added status check

# --- FastAPI App ---
app = FastAPI(
    title="Systemd Service Controller",
    description=f"API to control the '{ALLOWED_SERVICE_NAME}' service.",
    version="1.0.0"
)

# --- Security Dependency ---
async def verify_api_key(api_key: str = Security(api_key_header)):
    """Dependency to verify the API key."""
    if api_key != EXPECTED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

# --- Response Model ---
class ServiceResponse(BaseModel):
    service: str
    action: str
    success: bool
    message: str
    details: str | None = None # To hold command output or error details

# --- API Endpoint ---
@app.post(
    "/service/{action}", # Path parameter for action
    response_model=ServiceResponse,
    dependencies=[Depends(verify_api_key)] # Apply API Key security
)
async def control_service(action: ServiceAction):
    """
    Controls the predefined systemd service (armello_bot.service).
    Requires a valid API Key in the 'X-API-Key' header.
    Allowed actions: start, stop, restart, status.
    """
    service_name = ALLOWED_SERVICE_NAME # Hardcoded service name

    command = ["sudo", "/bin/systemctl", action.value, service_name]

    try:
        # Execute the command
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False, # Don't raise exception on non-zero exit, handle manually
            timeout=30 # Add a timeout
        )

        if result.returncode == 0:
            return ServiceResponse(
                service=service_name,
                action=action.value,
                success=True,
                message=f"Service '{service_name}' action '{action.value}' executed successfully.",
                details=result.stdout.strip() or result.stderr.strip() # Include output if any
            )
        else:
            # Command failed
            error_details = f"Error executing command: {' '.join(command)}\nReturn Code: {result.returncode}\nStderr: {result.stderr.strip()}\nStdout: {result.stdout.strip()}"
            print(error_details) # Log the detailed error server-side
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute '{action.value}' on service '{service_name}'. Check server logs.",
            )

    except FileNotFoundError:
        print(f"Error: 'sudo' or 'systemctl' command not found. Ensure they are in PATH.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: systemctl or sudo not found."
        )
    except subprocess.TimeoutExpired:
        print(f"Error: Command '{' '.join(command)}' timed out.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command '{action.value}' on service '{service_name}' timed out."
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}") # Log the exception
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred."
        )

# --- Add a simple root endpoint for testing ---
@app.get("/")
async def read_root():
    return {"message": f"Service Controller API for {ALLOWED_SERVICE_NAME} is running."}
