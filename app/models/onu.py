from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ONUSummary(BaseModel):
    port: str
    onu_id: int
    serial: str
    status: str = Field(description="Ex: online, offline, los, dying-gasp")
    name: Optional[str] = None


class ONUDetails(BaseModel):
    port: str
    onu_id: int
    serial: str
    status: str
    name: Optional[str] = None
    rx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica recebida na OLT em dBm")
    tx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica transmitida pela ONU em dBm")
    vlan: Optional[int] = None


class UnauthorizedONU(BaseModel):
    port: str
    serial: str
    model: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
