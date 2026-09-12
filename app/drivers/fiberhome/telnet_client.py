import logging
import socket
import time
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


class TelnetClient:
    """
    Cliente Telnet resiliente implementado sobre raw sockets TCP (compatível com Python 3.13+).
    Trata comandos de negociação IAC (0xFF) descartando ou rejeitando opções avançadas
    para garantir comunicação em texto limpo com OLTs (Fiberhome, etc).
    """

    def __init__(self, host: str, port: int = 23, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self) -> None:
        """Abre a conexão TCP com o concentrador."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))

    def read_until(
        self,
        matches: Union[str, bytes, List[Union[str, bytes]]],
        timeout: Optional[int] = None,
    ) -> bytes:
        """
        Lê dados do socket até encontrar um dos padrões informados ou estourar o timeout.
        Trata IAC (0xFF) Telnet internamente.
        """
        if not self.sock:
            raise ConnectionError("Socket Telnet não está conectado.")

        deadline = time.time() + (timeout or self.timeout)
        buffer = bytearray()

        if isinstance(matches, (str, bytes)):
            matches = [matches]

        byte_matches = [
            m.encode("ascii") if isinstance(m, str) else m for m in matches
        ]

        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break

                # Filtra caracteres de controle Telnet (IAC: 0xFF)
                clean_chunk = bytearray()
                i = 0
                while i < len(chunk):
                    if chunk[i] == 0xFF:  # IAC
                        if i + 1 < len(chunk) and chunk[i + 1] in (0xFB, 0xFC, 0xFD, 0xFE):  # WILL, WONT, DO, DONT
                            cmd = chunk[i + 1]
                            opt = chunk[i + 2] if i + 2 < len(chunk) else 0
                            # Responde WONT para DO (0xFD) e DONT para WILL (0xFB)
                            if cmd == 0xFD:
                                self.sock.sendall(bytes([0xFF, 0xFC, opt]))
                            elif cmd == 0xFB:
                                self.sock.sendall(bytes([0xFF, 0xFE, opt]))
                            i += 3
                            continue
                        elif i + 1 < len(chunk) and chunk[i + 1] == 0xF0:  # SE
                            i += 2
                            continue
                        else:
                            i += 2
                            continue
                    else:
                        clean_chunk.append(chunk[i])
                        i += 1

                buffer.extend(clean_chunk)
                for m in byte_matches:
                    if m in buffer:
                        return bytes(buffer)
            except socket.timeout:
                continue

        return bytes(buffer)

    def write(self, data: Union[str, bytes]) -> None:
        """Envia bytes ou string ASCII através do canal Telnet."""
        if not self.sock:
            raise ConnectionError("Socket Telnet não está conectado.")
        if isinstance(data, str):
            data = data.encode("ascii", errors="replace")
        self.sock.sendall(data)

    def close(self) -> None:
        """Encerra a conexão e libera o socket."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.debug(f"Exceção ao fechar socket Telnet: {e}")
            self.sock = None
