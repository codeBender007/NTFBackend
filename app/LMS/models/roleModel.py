from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)

    # Database does not have isActive column in MSSQL; expose as dynamic property
    @property
    def isActive(self) -> bool:
        return True

    # Relationships
    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    users = relationship(
        "User",
        back_populates="role_obj"
    )
