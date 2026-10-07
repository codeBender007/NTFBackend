from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    departmentId = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subDepartmentId = Column(Integer, ForeignKey("subDepartments.id"), nullable=False)
    lineId = Column(Integer, ForeignKey("lines.id"), nullable=False)
    machineName = Column(String(150), nullable=False)

    line = relationship("Line", back_populates="machines")