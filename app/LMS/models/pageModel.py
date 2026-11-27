import re
from typing import Optional
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    module = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    _pageKey = Column("pageKey", String(150), nullable=True, index=True)

    @property
    def pageKey(self) -> str:
        """
        Frontend route identifier / unique slug for access control guards (e.g. 'users', 'dojo_hiring').
        """
        if self._pageKey and self._pageKey.strip():
            return self._pageKey.strip()
        if not self.name:
            return ""
        return re.sub(r'[^a-zA-Z0-9]+', '_', self.name.strip().lower()).strip('_')

    @pageKey.setter
    def pageKey(self, value: Optional[str]):
        if value and str(value).strip():
            self._pageKey = re.sub(r'[^a-zA-Z0-9_]+', '_', str(value).strip().lower()).strip('_')
        else:
            self._pageKey = None

    @property
    def isActive(self) -> bool:
        """Database does not have isActive column in MSSQL; expose as dynamic property."""
        return True

    # Relationships
    permissions = relationship(
        "RolePermission",
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
