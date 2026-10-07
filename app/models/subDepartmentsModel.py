from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class SubDepartment(Base):
    __tablename__ = "subDepartments"

    id = Column(Integer, primary_key=True, index=True)
    departmentId = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subDepartmentName = Column(String(150), nullable=False)

    department = relationship("Department", back_populates="subDepartments")
    lines = relationship("Line", back_populates="subDepartment")