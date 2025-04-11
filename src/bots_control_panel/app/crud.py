# app/crud.py
from sqlalchemy.orm import Session
from . import models, schemas

def get_service_by_name(db: Session, name: str) -> models.Service | None:
    """Fetches a service by its unique name."""
    return db.query(models.Service).filter(models.Service.name == name).first()

def get_service_by_api_key(db: Session, api_key: str) -> models.Service | None:
    """Fetches a service by its unique API key."""
    # Note: In a real high-security scenario, compare keys using
    # a constant-time comparison function to prevent timing attacks.
    return db.query(models.Service).filter(models.Service.api_key == api_key).first()

def get_services(db: Session, skip: int = 0, limit: int = 100) -> list[models.Service]:
    """Fetches a list of services."""
    return db.query(models.Service).offset(skip).limit(limit).all()

def create_service(db: Session, service: schemas.ServiceCreate) -> models.Service:
    """Creates a new service entry in the database."""
    db_service = models.Service(name=service.name, api_key=service.api_key)
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    return db_service

# Add update/delete functions if needed
