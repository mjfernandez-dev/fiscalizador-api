"""
Middleware de autenticación.
Contiene el decorador para validar API keys.
"""
from functools import wraps
import hmac
from flask import request, jsonify
from app.config import API_KEY

def require_api_key(f):
    """Decorador para validar la API key en las rutas protegidas."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or not hmac.compare_digest(api_key, API_KEY):
            return jsonify({"error": "API key inválida"}), 401
        return f(*args, **kwargs)
    return decorated 