"""
Middleware de logging.
Contiene funciones para el registro de peticiones.
"""
import logging
from flask import request

def log_request_info():
    """Middleware para logging de seguridad de las peticiones."""
    if request.path != '/':  # No loguear peticiones a la interfaz web
        logging.info(
            f"Request: {request.method} {request.path} "
            f"from {request.remote_addr} "
            f"with headers {dict(request.headers)}"
        ) 