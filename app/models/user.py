import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserKind(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"
    SELLER = "seller"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    kind: Mapped[UserKind] = mapped_column(Enum(UserKind), index=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.ACTIVE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    employee_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    group_memberships: Mapped[list["GroupMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sellers_assigned: Mapped[list["EmployeeSellerAssignment"]] = relationship(
        foreign_keys="EmployeeSellerAssignment.employee_id",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    assigned_to_employees: Mapped[list["EmployeeSellerAssignment"]] = relationship(
        foreign_keys="EmployeeSellerAssignment.seller_id",
        back_populates="seller",
        cascade="all, delete-orphan",
    )
