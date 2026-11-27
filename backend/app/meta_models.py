from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class MetaLead(Base):
    __tablename__ = "meta_leads"

    lead_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    form_id: Mapped[str] = mapped_column(String(160))
    campaign_id: Mapped[str] = mapped_column(String(160))
    ad_id: Mapped[str | None] = mapped_column(String(160))
    submitted_at: Mapped[datetime]
    created_member: Mapped[bool]
