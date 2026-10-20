from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.hateoas import Link


class ONUMacEntry(BaseModel):
    mac_address: str = Field(description="Endereço MAC aprendido na ONU (formato XX:XX:XX:XX:XX:XX)")
    vlan: Optional[int] = Field(default=None, description="VLAN associada ao endereço MAC")
    port: Optional[str] = Field(default=None, description="Porta física/lógica UNI ou gemport na ONU")


class ONUSummary(BaseModel):
    port: str
    onu_id: int
    serial: str
    status: str = Field(description="Ex: online, offline, los, dying-gasp")
    name: Optional[str] = None
    vlan: Optional[int] = None
    last_down_cause: Optional[str] = Field(
        default=None,
        description="Causa da última queda (dying_gasp, los, lofi, admin_down, power_off, unknown)",
    )
    last_down_time: Optional[str] = Field(
        default=None,
        description="Horário reportado da última desconexão da ONU",
    )
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
    last_down_cause: Optional[str] = Field(
        default=None,
        description="Causa da última queda (dying_gasp, los, lofi, admin_down, power_off, unknown)",
    )
    last_down_time: Optional[str] = Field(
        default=None,
        description="Horário reportado da última desconexão da ONU",
    )
    mac_table: List[ONUMacEntry] = Field(
        default_factory=list,
        description="Tabela FDB/MAC aprendida nas portas LAN/Bridge da ONU",
    )
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}



class UnauthorizedONU(BaseModel):
    port: str
    serial: str
    model: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}

