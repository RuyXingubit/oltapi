from typing import Dict
from app.drivers.base import BaseOLTDriver
from app.drivers.registry import DriverRegistry
# Importa drivers homologados para acionar os decoradores de registro no DriverRegistry
import app.drivers.fiberhome.fiberhome_tl1  # noqa: F401
import app.drivers.vsol.vsol_v1600  # noqa: F401
from app.models.olt import OLTInDB


class DriverFactory:
    """Fábrica de drivers de OLT com resolução dinâmica via DriverRegistry."""

    _drivers_cache: Dict[str, BaseOLTDriver] = {}

    @classmethod
    def get_driver(cls, olt: OLTInDB) -> BaseOLTDriver:
        vendor = olt.vendor.value.lower() if hasattr(olt.vendor, "value") else str(olt.vendor).lower()
        model = olt.model.lower() if olt.model else ""

        key = f"{vendor}_{model}"
        if key in cls._drivers_cache:
            return cls._drivers_cache[key]

        driver_cls = DriverRegistry.get_driver_class(vendor=vendor, model=model)
        try:
            driver = driver_cls(model_name=olt.model)
        except TypeError:
            driver = driver_cls()

        cls._drivers_cache[key] = driver
        return driver
