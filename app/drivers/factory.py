from typing import Dict
from app.drivers.base import BaseOLTDriver
from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.drivers.huawei.huawei_vrp import HuaweiVRPDriver
from app.drivers.intelbras.intelbras_8820 import Intelbras8820Driver
from app.drivers.intelbras.intelbras_gseries import IntelbrasGSeriesDriver
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
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
            elif "g08" in model or "g8" in model:
                driver = IntelbrasGSeriesDriver(total_pons=8, model_name="G08")
                cls._drivers_cache[key] = driver
                return driver
            elif "g16" in model:
                driver = IntelbrasGSeriesDriver(total_pons=16, model_name="G16")
                cls._drivers_cache[key] = driver
                return driver
            elif "4840" in model:
                # Placeholder para driver 4840
                raise NotImplementedError("Driver Intelbras 4840 planejado para o próximo ciclo de entrega.")

        elif vendor == OLTVendor.HUAWEI.value:
            if any(m in model for m in ["5800", "5608", "5680", "5683", "vrp", "smartax"]):
                driver = HuaweiVRPDriver()
                cls._drivers_cache[key] = driver
                return driver
            # Padrão para OLTs Huawei genéricas VRP
            driver = HuaweiVRPDriver()
            cls._drivers_cache[key] = driver
            return driver

        elif vendor == OLTVendor.FIBERHOME.value:
            driver = FiberhomeTL1Driver()
            cls._drivers_cache[key] = driver
            return driver

        elif vendor == OLTVendor.VSOL.value:
            driver = VSOLV1600Driver(model_name=olt.model)
            cls._drivers_cache[key] = driver
            return driver

        elif vendor == OLTVendor.PARKS.value:
            raise NotImplementedError("Driver Parks Fiberlink planejado para o próximo ciclo de entrega.")

        raise ValueError(f"Nenhum driver compatível encontrado para o fabricante '{olt.vendor}' e modelo '{olt.model}'.")
