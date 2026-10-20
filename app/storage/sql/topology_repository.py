from datetime import datetime, timezone
from typing import List, Optional

from app.core.uuid import generate_uuid7
from app.db.models import (
    NetworkZoneModel,
    ONUInventoryModel,
    OpticalDistributionBoxModel,
)
from app.db.session import SessionLocal
from app.models.topology import (
    NetworkZoneCreate,
    NetworkZoneItem,
    ODBHealthNode,
    ONUTopologyAssignRequest,
    OpticalDistributionBoxCreate,
    OpticalDistributionBoxItem,
    TopologyHealthMapResponse,
)


class SQLTopologyRepository:
    """Repositório relacional para Topologia Passiva FTTH: Zonas, CTOs (ODBs), Splitters e Mapa de Saúde (Fase 4)."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_zone(self, m: NetworkZoneModel, odb_count: int = 0, onu_count: int = 0) -> NetworkZoneItem:
        return NetworkZoneItem(
            id=m.id,
            name=m.name,
            sector=m.sector,
            city=m.city,
            description=m.description,
            odb_count=odb_count,
            onu_count=onu_count,
            created_at=m.created_at,
        )

    def _to_odb(self, m: OpticalDistributionBoxModel, occupied_ports: List[int], used_count: int) -> OpticalDistributionBoxItem:
        cap = m.splitter_capacity or 16
        return OpticalDistributionBoxItem(
            id=m.id,
            code=m.code,
            name=m.name,
            zone_id=m.zone_id,
            olt_id=m.olt_id,
            pon_port=m.pon_port,
            splitter_capacity=cap,
            used_ports=used_count,
            available_ports=max(0, cap - used_count),
            occupied_splitter_ports=sorted(occupied_ports),
            latitude=m.latitude,
            longitude=m.longitude,
            address=m.address,
            notes=m.notes,
            created_at=m.created_at,
        )

    # --- Zonas de Rede ---

    def list_zones(self) -> List[NetworkZoneItem]:
        with self.session_factory() as db:
            zones = db.query(NetworkZoneModel).order_by(NetworkZoneModel.name.asc()).all()
            items: List[NetworkZoneItem] = []
            for z in zones:
                odb_c = (
                    db.query(OpticalDistributionBoxModel)
                    .filter(OpticalDistributionBoxModel.zone_id == z.id)
                    .count()
                )
                onu_c = (
                    db.query(ONUInventoryModel)
                    .filter(ONUInventoryModel.zone_id == z.id)
                    .count()
                )
                items.append(self._to_zone(z, odb_count=odb_c, onu_count=onu_c))
            return items

    def get_zone(self, zone_id: str) -> Optional[NetworkZoneItem]:
        with self.session_factory() as db:
            z = db.query(NetworkZoneModel).filter(NetworkZoneModel.id == zone_id).first()
            if not z:
                return None
            odb_c = (
                db.query(OpticalDistributionBoxModel)
                .filter(OpticalDistributionBoxModel.zone_id == z.id)
                .count()
            )
            onu_c = (
                db.query(ONUInventoryModel)
                .filter(ONUInventoryModel.zone_id == z.id)
                .count()
            )
            return self._to_zone(z, odb_count=odb_c, onu_count=onu_c)

    def create_zone(self, req: NetworkZoneCreate) -> NetworkZoneItem:
        clean_name = req.name.strip()
        with self.session_factory() as db:
            existing = db.query(NetworkZoneModel).filter(NetworkZoneModel.name == clean_name).first()
            if existing:
                raise ValueError(f"Já existe uma Zona de Rede com o nome '{clean_name}'.")
            m = NetworkZoneModel(
                id=generate_uuid7(),
                name=clean_name,
                sector=req.sector.strip() if req.sector else None,
                city=req.city.strip() if req.city else None,
                description=req.description.strip() if req.description else None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_zone(m)

    def delete_zone(self, zone_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(NetworkZoneModel).filter(NetworkZoneModel.id == zone_id).first()
            if not m:
                return False
            db.delete(m)
            db.commit()
            return True

    # --- CTOs / ODBs ---

    def _hydrate_odb(self, db, m: OpticalDistributionBoxModel) -> OpticalDistributionBoxItem:
        onus = db.query(ONUInventoryModel).filter(ONUInventoryModel.odb_id == m.id).all()
        occupied = [o.odb_splitter_port for o in onus if o.odb_splitter_port is not None]
        return self._to_odb(m, occupied_ports=occupied, used_count=len(onus))

    def list_odbs(
        self,
        zone_id: Optional[str] = None,
        olt_id: Optional[str] = None,
    ) -> List[OpticalDistributionBoxItem]:
        with self.session_factory() as db:
            q = db.query(OpticalDistributionBoxModel)
            if zone_id:
                q = q.filter(OpticalDistributionBoxModel.zone_id == zone_id)
            if olt_id:
                q = q.filter(OpticalDistributionBoxModel.olt_id == olt_id)
            rows = q.order_by(OpticalDistributionBoxModel.code.asc()).all()
            return [self._hydrate_odb(db, r) for r in rows]

    def get_odb(self, odb_id: str) -> Optional[OpticalDistributionBoxItem]:
        with self.session_factory() as db:
            m = (
                db.query(OpticalDistributionBoxModel)
                .filter(OpticalDistributionBoxModel.id == odb_id)
                .first()
            )
            return self._hydrate_odb(db, m) if m else None

    def create_odb(self, req: OpticalDistributionBoxCreate) -> OpticalDistributionBoxItem:
        clean_code = req.code.strip().upper()
        with self.session_factory() as db:
            existing = (
                db.query(OpticalDistributionBoxModel)
                .filter(OpticalDistributionBoxModel.code == clean_code)
                .first()
            )
            if existing:
                raise ValueError(f"Já existe uma CTO/ODB com o código '{clean_code}'.")
            if req.zone_id:
                zone = db.query(NetworkZoneModel).filter(NetworkZoneModel.id == req.zone_id).first()
                if not zone:
                    raise ValueError(f"Zona de Rede '{req.zone_id}' não encontrada.")

            m = OpticalDistributionBoxModel(
                id=generate_uuid7(),
                code=clean_code,
                name=req.name.strip(),
                zone_id=req.zone_id,
                olt_id=req.olt_id,
                pon_port=req.pon_port.strip() if req.pon_port else None,
                splitter_capacity=req.splitter_capacity,
                latitude=req.latitude,
                longitude=req.longitude,
                address=req.address.strip() if req.address else None,
                notes=req.notes.strip() if req.notes else None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._hydrate_odb(db, m)

    def delete_odb(self, odb_id: str) -> bool:
        with self.session_factory() as db:
            m = (
                db.query(OpticalDistributionBoxModel)
                .filter(OpticalDistributionBoxModel.id == odb_id)
                .first()
            )
            if not m:
                return False
            db.delete(m)
            db.commit()
            return True

    def validate_and_assign_onu_topology(
        self,
        serial: str,
        req: ONUTopologyAssignRequest,
    ) -> dict:
        """
        Valida capacidade e colisão de porta de splitter na CTO/ODB antes de vincular a ONU.
        Retorna os campos validados para atualização no inventário.
        """
        with self.session_factory() as db:
            target_zone_id = req.zone_id
            if req.odb_id:
                odb = (
                    db.query(OpticalDistributionBoxModel)
                    .filter(OpticalDistributionBoxModel.id == req.odb_id)
                    .first()
                )
                if not odb:
                    raise ValueError(f"CTO/ODB '{req.odb_id}' não encontrada.")
                if not target_zone_id and odb.zone_id:
                    target_zone_id = odb.zone_id

                if req.odb_splitter_port is not None:
                    if req.odb_splitter_port < 1 or req.odb_splitter_port > odb.splitter_capacity:
                        raise ValueError(
                            f"Porta do splitter ({req.odb_splitter_port}) excede a capacidade da CTO '{odb.code}' (1..{odb.splitter_capacity})."
                        )
                    collision = (
                        db.query(ONUInventoryModel)
                        .filter(
                            ONUInventoryModel.odb_id == odb.id,
                            ONUInventoryModel.odb_splitter_port == req.odb_splitter_port,
                            ONUInventoryModel.serial != serial,
                        )
                        .first()
                    )
                    if collision:
                        raise ValueError(
                            f"Porta {req.odb_splitter_port} da CTO '{odb.code}' já está ocupada pela ONU '{collision.serial}'."
                        )

            return {
                "zone_id": target_zone_id,
                "odb_id": req.odb_id,
                "odb_splitter_port": req.odb_splitter_port,
                "latitude": req.latitude,
                "longitude": req.longitude,
            }

    def get_topology_health_map(
        self,
        olt_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> TopologyHealthMapResponse:
        """
        Correlaciona as ONUs de cada CTO/ODB com suas potências ópticas e causas de desconexão:
        - Maioria em 'los'/'lofi' -> 'fiber_cut' (Rompimento de Fibra / Drop Troncal)
        - Maioria em 'dying_gasp'/'power_off' -> 'power_outage' (Queda de Energia Elétrica na Região)
        - Qualquer ONU com sinal <= -25.5 dBm -> 'degraded' (Atenuação na Caixa/Fusão)
        - Caso contrário -> 'healthy'
        """
        with self.session_factory() as db:
            total_zones = db.query(NetworkZoneModel).count()
            zone_map = {z.id: z.name for z in db.query(NetworkZoneModel).all()}

            q = db.query(OpticalDistributionBoxModel)
            if olt_id:
                q = q.filter(OpticalDistributionBoxModel.olt_id == olt_id)
            if zone_id:
                q = q.filter(OpticalDistributionBoxModel.zone_id == zone_id)
            odbs = q.order_by(OpticalDistributionBoxModel.code.asc()).all()

            nodes: List[ODBHealthNode] = []
            healthy_c = 0
            degraded_c = 0
            power_c = 0
            fiber_c = 0

            for odb in odbs:
                onus = db.query(ONUInventoryModel).filter(ONUInventoryModel.odb_id == odb.id).all()
                total_o = len(onus)
                dying_c = 0
                los_c = 0
                deg_c = 0
                online_c = 0

                for o in onus:
                    cause = (o.last_down_cause or "").lower()
                    if cause in ("dying_gasp", "power_off"):
                        dying_c += 1
                    elif cause in ("los", "lofi"):
                        los_c += 1
                    else:
                        online_c += 1

                    if o.last_rx_power_dbm is not None and o.last_rx_power_dbm <= -25.5:
                        deg_c += 1

                status_str = "healthy"
                summary = "Operação óptica normal"

                if total_o > 0 and los_c >= max(1, (total_o + 1) // 2):
                    status_str = "fiber_cut"
                    summary = f"Possível rompimento óptico na CTO/PON ({los_c}/{total_o} ONUs em LoS)"
                    fiber_c += 1
                elif total_o > 0 and dying_c >= max(1, (total_o + 1) // 2):
                    status_str = "power_outage"
                    summary = f"Queda elétrica coletiva no setor ({dying_c}/{total_o} ONUs em Dying Gasp)"
                    power_c += 1
                elif deg_c > 0 or los_c > 0:
                    status_str = "degraded"
                    summary = f"Atenuação ou falha pontual ({deg_c} com sinal baixo, {los_c} em LoS)"
                    degraded_c += 1
                else:
                    healthy_c += 1

                nodes.append(
                    ODBHealthNode(
                        odb_id=odb.id,
                        code=odb.code,
                        name=odb.name,
                        zone_id=odb.zone_id,
                        zone_name=zone_map.get(odb.zone_id) if odb.zone_id else None,
                        olt_id=odb.olt_id,
                        pon_port=odb.pon_port,
                        splitter_capacity=odb.splitter_capacity,
                        total_onus=total_o,
                        online_onus=online_c,
                        dying_gasp_onus=dying_c,
                        los_onus=los_c,
                        degraded_onus=deg_c,
                        health_status=status_str,
                        diagnosis_summary=summary,
                        latitude=odb.latitude,
                        longitude=odb.longitude,
                    )
                )

            return TopologyHealthMapResponse(
                total_zones=total_zones,
                total_odbs=len(odbs),
                healthy_odbs=healthy_c,
                degraded_odbs=degraded_c,
                power_outage_odbs=power_c,
                fiber_cut_odbs=fiber_c,
                nodes=nodes,
            )
