from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    departmentName = Column(String(150), nullable=False)

    subDepartments = relationship("SubDepartment", back_populates="department")