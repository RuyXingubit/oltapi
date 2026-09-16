import logging
from typing import Callable, Dict, List, Optional, Type, Union
from app.models.olt import OLTVendor

logger = logging.getLogger(__name__)


class DriverRegistry:
    """
    Registro desacoplado de drivers de OLT (Inversão de Dependência & Open/Closed Principle).
    Permite que novos fabricantes se registrem de forma plug-and-play através do decorador:
        @DriverRegistry.register(vendor=OLTVendor.VSOL, models=["V1600GT", ...])
        class VSOLV1600Driver(BaseOLTDriver): ...
    """

    _registry: Dict[str, Dict[str, Type]] = {}
    _default_by_vendor: Dict[str, Type] = {}

    @classmethod
    def register(
        cls,
        vendor: Union[OLTVendor, str],
        models: Optional[List[str]] = None,
        is_default_for_vendor: bool = True,
    ) -> Callable[[Type], Type]:
        """
        Decorador de registro de driver.
        """
        vendor_key = vendor.value.lower() if hasattr(vendor, "value") else str(vendor).lower()

        def decorator(driver_cls: Type) -> Type:
            if vendor_key not in cls._registry:
                cls._registry[vendor_key] = {}

            if models:
                for model in models:
                    model_key = model.strip().lower()
                    cls._registry[vendor_key][model_key] = driver_cls

            if is_default_for_vendor or vendor_key not in cls._default_by_vendor:
                cls._default_by_vendor[vendor_key] = driver_cls

            logger.debug(f"[DriverRegistry] Driver registrado: {vendor_key} (Modelos: {models}) -> {driver_cls.__name__}")
            return driver_cls

        return decorator

    @classmethod
    def get_driver_class(
        cls,
        vendor: Union[OLTVendor, str],
        model: Optional[str] = None,
    ) -> Type:
        """
        Resolve dinamicamente a classe do driver com base no vendor e modelo.
        """
        vendor_key = vendor.value.lower() if hasattr(vendor, "value") else str(vendor).lower()
        models_map = cls._registry.get(vendor_key, {})

        if model:
            model_key = model.strip().lower()
            # 1. Busca exata de modelo
            if model_key in models_map:
                return models_map[model_key]

            # 2. Busca por substring ou padrão
            for pattern, driver_cls in models_map.items():
                if pattern in model_key or model_key in pattern:
                    return driver_cls

        # 3. Fallback para driver padrão do fabricante
        if vendor_key in cls._default_by_vendor:
            return cls._default_by_vendor[vendor_key]

        raise ValueError(
            f"Nenhum driver compatível encontrado no registro para o fabricante '{vendor}' "
            f"(Modelo informado: '{model}'). Fabricantes ativos homologados: {list(cls._default_by_vendor.keys())}"
        )

    @classmethod
    def list_supported_vendors(cls) -> List[str]:
        """Retorna a lista de fabricantes ativos registrados."""
        return list(cls._default_by_vendor.keys())
