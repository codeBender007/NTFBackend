from sqlalchemy import Column, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("roleId", "pageId", name="uq_role_page"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    roleId = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    pageId = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)

    canView = Column(Boolean, default=False, nullable=True)
    canCreate = Column(Boolean, default=False, nullable=True)
    canEdit = Column(Boolean, default=False, nullable=True)
    canDelete = Column(Boolean, default=False, nullable=True)
    canUploadExcel = Column(Boolean, default=False, nullable=True)

    # Relationships
    role = relationship("Role", back_populates="permissions")
    page = relationship("Page", back_populates="permissions")
