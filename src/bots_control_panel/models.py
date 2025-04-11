# app/models.py
from sqlalchemy import Column, Integer, String, UniqueConstraint
from .database import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False) # Store securely!

    # Optional: Add constraints if needed, e.g. name format
    # __table_args__ = (UniqueConstraint('name', name='uq_service_name'), )

    def __repr__(self):
        return f"<Service(name='{self.name}')>"
