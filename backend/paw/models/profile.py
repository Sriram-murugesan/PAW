from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from paw.db.base import Base, IdMixin, TimestampMixin


class Profile(IdMixin, TimestampMixin, Base):
    __tablename__ = "profile"

    # A constant unique key keeps this to one row.
    singleton: Mapped[int] = mapped_column(unique=True, default=1)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    profile_data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    version: Mapped[int] = mapped_column(default=0)
