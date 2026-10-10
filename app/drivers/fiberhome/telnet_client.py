"""
Re-exportação de TelnetClient para manter compatibilidade retroativa
com códigos legados ou testes existentes.
A implementação canônica reside em app.core.telnet.
"""
from app.core.telnet import TelnetClient

__all__ = ["TelnetClient"]
