import re
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    module = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)

    @property
    def pageKey(self) -> str:
        """
        Derives canonical pageKey from page name (e.g. 'Users' -> 'users', 'DOJO Hiring' -> 'dojo_hiring').
        """
        if not self.name:
            return ""
        clean = re.sub(r'[^a-zA-Z0-9]+', '_', self.name.strip().lower()).strip('_')
        return clean

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
