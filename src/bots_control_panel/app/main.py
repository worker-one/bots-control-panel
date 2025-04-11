# app/main.py
import subprocess
import logging
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates # Use Jinja2 for minor flexibility

from sqlalchemy.orm import Session

from . import crud, models, schemas, database

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Create DB Tables on Startup ---
# In production, use migrations (Alembic). For simplicity here, create on start.
# Note: Calling this here means it runs every time the app starts.
# It's safe because `create_all` doesn't recreate existing tables.
database.create_db_and_tables()


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Multi-Service Systemd Controller",
    description="Control multiple systemd services via API with unique keys.",
    version="1.0.1" # Increment version
)

# --- Template Setup ---
# Use Jinja2Templates for potential future enhancements, though simple read_text works too
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_path)


# --- Helper Function for Systemd Control ---
def _run_systemctl_command(action: schemas.ServiceAction, service_name: str) -> schemas.ServiceResponse:
    """
    Executes the systemctl command securely.
    Requires proper sudoers configuration.
    """
    command = ["sudo", "/bin/systemctl", action.value, service_name]
    success = False
    message = ""
    details = ""

    logger.info(f"Executing command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False, # Handle non-zero exit code manually
            timeout=30 # Add a timeout
        )

        details = f"STDOUT:\n{result.stdout.strip()}\nSTDERR:\n{result.stderr.strip()}"
        logger.debug(f"Command Result for {service_name} ({action.value}):\n{details}")

        if result.returncode == 0:
            success = True
            message = f"Service '{service_name}' action '{action.value}' executed successfully."
            logger.info(message)
        else:
            message = f"Failed to execute '{action.value}' on service '{service_name}'. Return code: {result.returncode}."
            logger.error(f"{message} Details:\n{details}")

    except FileNotFoundError:
        message = "Server configuration error: 'sudo' or 'systemctl' command not found."
        logger.exception(message) # Log full traceback
        details = "Ensure sudo and systemctl are installed and in the PATH for the user running the FastAPI app."
    except subprocess.TimeoutExpired:
        message = f"Command '{' '.join(command)}' timed out after 30 seconds."
        logger.warning(message)
        details = "The service might be unresponsive or the command took too long."
    except Exception as e:
        message = f"An unexpected error occurred while running the command: {e}"
        logger.exception(message) # Log full traceback
        details = str(e)

    return schemas.ServiceResponse(
        service=service_name,
        action=action.value,
        success=success,
        message=message,
        details=details
    )


# --- API Key Verification (Dependency-like function) ---
async def verify_api_key_for_service(
    service_name: str,
    x_api_key: str | None = Header(None, description="The API Key for the specific service"),
    db: Session = Depends(database.get_db)
) -> models.Service:
    """
    Verifies the provided X-API-Key against the key stored for the service_name.
    Raises HTTPException 401 or 404 if validation fails.
    Returns the validated Service model instance.
    """
    if not x_api_key:
        logger.warning(f"Missing X-API-Key header for service: {service_name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    db_service = crud.get_service_by_name(db, name=service_name)

    if not db_service:
        logger.warning(f"Service not found in DB: {service_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_name}' not found or not managed by this API."
        )

    # SECURITY: Use constant time comparison in production if possible
    if db_service.api_key != x_api_key:
        logger.warning(f"Invalid API Key provided for service: {service_name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key for the specified service",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.info(f"API Key validated successfully for service: {service_name}")
    return db_service


# --- API Endpoints ---

@app.post(
    "/api/services/{service_name}/{action}",
    response_model=schemas.ServiceResponse,
    tags=["Service Control"],
    summary="Control a specific systemd service"
)
async def control_service_api(
    service_name: str,
    action: schemas.ServiceAction,
    # Depends runs verification, returns db_service if valid, raises exception otherwise
    db_service: models.Service = Depends(verify_api_key_for_service)
):
    """
    Controls the specified systemd service (`start`, `stop`, `restart`, `status`).

    Requires a valid `X-API-Key` header corresponding to the `service_name`.

    **Important:** The user running this FastAPI application needs passwordless
    `sudo` permission for the specific `systemctl [action] [service_name]` commands
    it needs to execute. Configure `/etc/sudoers` carefully.
    """
    # Service name validation already happened implicitly in verify_api_key_for_service
    # API key validation also happened there.
    logger.info(f"API request received for service '{service_name}', action '{action.value}'")
    return _run_systemctl_command(action=action, service_name=db_service.name)


# --- UI Endpoints ---

@app.get(
    "/ui/services/{service_name}",
    response_class=HTMLResponse,
    tags=["Web UI"],
    summary="Web UI to control a specific service"
)
async def get_service_ui(
    request: Request, # Needed by Jinja2Templates
    service_name: str,
    db: Session = Depends(database.get_db)
):
    """
    Serves the HTML user interface for controlling a specific service.
    The service must exist in the database.
    Authentication (API Key) is handled by the JavaScript within the UI
    when it calls the `/api/services/...` endpoint.
    """
    db_service = crud.get_service_by_name(db, name=service_name)
    if not db_service:
        logger.warning(f"UI requested for non-existent service: {service_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_name}' not found."
        )

    logger.info(f"Serving UI for service: {service_name}")
    # Pass service name to the template context
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "service_name": service_name}
    )

# --- Optional: Endpoint to add services (for setup/admin) ---
# PROTECT THIS ENDPOINT IN PRODUCTION (e.g., admin auth, IP restriction)
@app.post(
    "/admin/services/",
    response_model=schemas.Service,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
    summary="Add a new service to manage (Admin Only)"
)
async def create_new_service(
    service: schemas.ServiceCreate,
    db: Session = Depends(database.get_db)
    # TODO: Add authentication/authorization for this endpoint!
):
    """
    Adds a new service and its API key to the database.
    **WARNING:** This endpoint should be secured in a production environment.
    """
    db_service = crud.get_service_by_name(db, name=service.name)
    if db_service:
        logger.warning(f"Attempted to create duplicate service: {service.name}")
        raise HTTPException(status_code=400, detail=f"Service '{service.name}' already registered.")

    db_api_key = crud.get_service_by_api_key(db, api_key=service.api_key)
    if db_api_key:
         logger.warning(f"Attempted to use duplicate API key for service: {service.name}")
         raise HTTPException(status_code=400, detail="API key already in use.")

    logger.info(f"Creating new service registration: {service.name}")
    new_service = crud.create_service(db=db, service=service)
    logger.info(f"Service '{new_service.name}' created successfully with ID {new_service.id}.")
    return new_service

@app.get(
    "/admin/services/",
    response_model=list[schemas.Service],
    tags=["Admin"],
    summary="List managed services (Admin Only)"
)
async def list_managed_services(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db)
    # TODO: Add authentication/authorization for this endpoint!
):
    """Lists services currently managed by the API."""
    services = crud.get_services(db, skip=skip, limit=limit)
    return services


# --- Root Redirect ---
@app.get("/", include_in_schema=False)
async def root_redirect():
    # Redirect to API docs or a landing page
    return RedirectResponse(url="/docs")
