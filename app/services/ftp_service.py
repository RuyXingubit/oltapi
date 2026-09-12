import ftplib
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FTPService:
    """Serviço de operações em servidores FTP para transferência de arquivos de backup."""

    @staticmethod
    def download_file(
        host: str,
        port: int,
        username: str,
        password: str,
        remote_filename: str,
        base_path: str = "/",
        timeout: int = 20,
    ) -> str:
        """
        Conecta ao servidor FTP, baixa o arquivo indicado e retorna seu conteúdo como texto decodificado.
        """
        ftp = ftplib.FTP(timeout=timeout)
        try:
            ftp.connect(host, port)
            ftp.login(username, password)

            if base_path and base_path != "/":
                ftp.cwd(base_path)

            buffer = io.BytesIO()
            ftp.retrbinary(f"RETR {remote_filename}", buffer.write)
            raw_data = buffer.getvalue()

            try:
                content = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_data.decode("latin-1", errors="replace")

            return content
        finally:
            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass

    @staticmethod
    def upload_file(
        host: str,
        port: int,
        username: str,
        password: str,
        remote_filename: str,
        content: str,
        base_path: str = "/",
        timeout: int = 20,
    ) -> bool:
        """
        Faz upload de conteúdo textual para o servidor FTP.
        """
        ftp = ftplib.FTP(timeout=timeout)
        try:
            ftp.connect(host, port)
            ftp.login(username, password)

            if base_path and base_path != "/":
                ftp.cwd(base_path)

            data = content.encode("utf-8")
            buffer = io.BytesIO(data)
            ftp.storbinary(f"STOR {remote_filename}", buffer)
            return True
        finally:
            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass

    @staticmethod
    def delete_file(
        host: str,
        port: int,
        username: str,
        password: str,
        remote_filename: str,
        base_path: str = "/",
        timeout: int = 15,
    ) -> bool:
        """
        Remove um arquivo do servidor FTP caso exista.
        """
        ftp = ftplib.FTP(timeout=timeout)
        try:
            ftp.connect(host, port)
            ftp.login(username, password)

            if base_path and base_path != "/":
                ftp.cwd(base_path)

            ftp.delete(remote_filename)
            return True
        except Exception as e:
            logger.warning(f"Não foi possível remover o arquivo '{remote_filename}' no FTP {host}: {e}")
            return False
        finally:
            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass
