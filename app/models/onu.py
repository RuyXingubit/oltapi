from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.models.hateoas import Link


class ONUSummary(BaseModel):
    port: str
    onu_id: int
    serial: str
    status: str = Field(description="Ex: online, offline, los, dying-gasp")
    name: Optional[str] = None
    vlan: Optional[int] = None
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ONUDetails(BaseModel):
    port: str
    onu_id: int
    serial: str
    status: str
    rx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica recebida na ONU em dBm (Downlink)")
    tx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica transmitida pela ONU em dBm")
    olt_rx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica recebida na OLT vinda da ONU em dBm (Uplink)")
    vlan: Optional[int] = None
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}



class UnauthorizedONU(BaseModel):
    port: str
    serial: str
    model: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}

