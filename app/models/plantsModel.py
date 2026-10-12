from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, index=True)
    plantName = Column(String(150), nullable=False)

    departments = relationship("Department", back_populates="plant", cascade="all, delete-orphan")
