from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Line(Base):
    __tablename__ = "lines"

    id = Column(Integer, primary_key=True, index=True)
    plantId = Column(Integer, ForeignKey("plants.id"), nullable=False)
    departmentId = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subDepartmentId = Column(Integer, ForeignKey("subDepartments.id"), nullable=False)
    lineName = Column(String(150), nullable=False)

    plant = relationship("Plant", foreign_keys=[plantId])
    department = relationship("Department", foreign_keys=[departmentId])
    subDepartment = relationship("SubDepartment", back_populates="lines", foreign_keys=[subDepartmentId])
    machines = relationship(
        "Machine",
        back_populates="line",
        foreign_keys="[Machine.lineId]",
        cascade="all, delete-orphan"
    )