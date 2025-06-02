"""
Este archivo ha sido deprecado.
Toda la configuración se ha movido a app/config/__init__.py
"""
from app.config import CERT, KEY, CUIT, API_KEY, TOKEN_EXPIRY_MINUTES, MAX_REQUESTS_PER_MINUTE, ALLOWED_ORIGINS

# Re-exportar las variables para mantener compatibilidad
__all__ = ['CERT', 'KEY', 'CUIT', 'API_KEY', 'TOKEN_EXPIRY_MINUTES', 'MAX_REQUESTS_PER_MINUTE', 'ALLOWED_ORIGINS']
