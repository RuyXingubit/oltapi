from typing import Dict
from app.drivers.base import BaseOLTDriver
from app.drivers.intelbras.intelbras_8820 import Intelbras8820Driver
from app.models.olt import OLTInDB, OLTVendor


class DriverFactory:
    """Fábrica de drivers de OLT responsável por instanciar o driver adequado a cada fabricante e modelo."""

    _drivers_cache: Dict[str, BaseOLTDriver] = {}

    @classmethod
    def get_driver(cls, olt: OLTInDB) -> BaseOLTDriver:
        vendor = olt.vendor.lower()
        model = olt.model.lower()

        key = f"{vendor}_{model}"
        if key in cls._drivers_cache:
            return cls._drivers_cache[key]

        if vendor == OLTVendor.INTELBRAS.value:
            if "8820" in model:
                driver = Intelbras8820Driver()
                cls._drivers_cache[key] = driver
                return driver
            elif "g16" in model:
                # Placeholder para driver G16 (próxima fase do roadmap)
                raise NotImplementedError("Driver Intelbras G16 planejado para o próximo ciclo de entrega.")
            elif "4840" in model:
                # Placeholder para driver 4840
                raise NotImplementedError("Driver Intelbras 4840 planejado para o próximo ciclo de entrega.")

        elif vendor == OLTVendor.HUAWEI.value:
            raise NotImplementedError("Driver Huawei MA5800 planejado para o próximo ciclo de entrega.")

        elif vendor == OLTVendor.FIBERHOME.value:
            raise NotImplementedError("Driver Fiberhome TL1 planejado para o próximo ciclo de entrega.")

        elif vendor == OLTVendor.PARKS.value:
            raise NotImplementedError("Driver Parks Fiberlink planejado para o próximo ciclo de entrega.")

        raise ValueError(f"Nenhum driver compatível encontrado para o fabricante '{olt.vendor}' e modelo '{olt.model}'.")
