from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    plantId = Column(Integer, ForeignKey("plants.id"), nullable=False)
    departmentName = Column(String(150), nullable=False)

    plant = relationship("Plant", back_populates="departments")
    subDepartments = relationship(
        "SubDepartment",
        back_populates="department",
        foreign_keys="[SubDepartment.departmentId]",
        cascade="all, delete-orphan"
    )