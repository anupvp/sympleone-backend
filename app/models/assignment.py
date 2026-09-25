import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeeSellerAssignment(Base):
    """Direct seller accounts assigned to an employee (outside or in addition to groups)."""

    __tablename__ = "employee_seller_assignments"
    __table_args__ = (UniqueConstraint("employee_id", "seller_id", name="uq_employee_seller"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped["User"] = relationship(
        foreign_keys=[employee_id], back_populates="sellers_assigned"
    )
    seller: Mapped["User"] = relationship(
        foreign_keys=[seller_id], back_populates="assigned_to_employees"
    )


from app.models.user import User  # noqa: E402
