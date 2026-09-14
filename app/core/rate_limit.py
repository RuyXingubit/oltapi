from slowapi import Limiter
from slowapi.util import get_remote_address

# Instância compartilhada do limitador de taxa de requisições (Rate Limiter)
limiter = Limiter(key_func=get_remote_address, default_limits=[])
