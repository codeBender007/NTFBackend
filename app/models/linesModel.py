# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Line(Base):
    __tablename__ = "lines"

    id = Column(Integer, primary_key=True, index=True)
    departmentId = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subDepartmentId = Column(Integer, ForeignKey("subDepartments.id"), nullable=False)
    lineName = Column(String(150), nullable=False)

    subDepartment = relationship("SubDepartment", back_populates="lines")
    machines = relationship("Machine", back_populates="line")