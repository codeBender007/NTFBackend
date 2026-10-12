from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class SubDepartment(Base):
    __tablename__ = "subDepartments"

    id = Column(Integer, primary_key=True, index=True)
    plantId = Column(Integer, ForeignKey("plants.id"), nullable=False)
    departmentId = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subDepartmentName = Column(String(150), nullable=False)

    plant = relationship("Plant", foreign_keys=[plantId])
    department = relationship("Department", back_populates="subDepartments", foreign_keys=[departmentId])
    lines = relationship(
        "Line",
        back_populates="subDepartment",
        foreign_keys="[Line.subDepartmentId]",
        cascade="all, delete-orphan"
    )