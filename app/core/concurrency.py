import asyncio
from typing import Dict


class OLTConcurrencyManager:
    """
    Gerenciador de concorrência por OLT física.
    Evita exaustão de sessões VTY (Telnet/SSH) e saturação da CPU da controladora
    serializando requisições intensivas direcionadas ao mesmo chassi.
    """

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}

    def get_lock(self, olt_id: str) -> asyncio.Lock:
        if olt_id not in self._locks:
            self._locks[olt_id] = asyncio.Lock()
        return self._locks[olt_id]


olt_concurrency_manager = OLTConcurrencyManager()
