"""
Inicialización de la aplicación Flask.
Configura la aplicación y registra los blueprints.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import config, ALLOWED_ORIGINS, MAX_REQUESTS_PER_MINUTE
from app.middleware import log_request_info
from app.routes.afip import bp as afip_bp

def create_app(config_name='default'):
    """Crea y configura la aplicación Flask."""
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(config[config_name])
    
    # Configurar CORS
    CORS(app, resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST"],
            "allow_headers": ["Content-Type", "X-API-Key"]
        }
    })
    
    # Configurar rate limiting global
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{MAX_REQUESTS_PER_MINUTE} per minute"]
    )
    
    # Registrar blueprint de AFIP
    app.register_blueprint(afip_bp)
    
    # Rutas web directas
    @app.route("/")
    def interfaz_web():
        """Endpoint para servir la interfaz web."""
        return send_from_directory(os.path.dirname(os.path.dirname(__file__)), "interface.html")

    @app.route("/favicon.ico")
    def favicon():
        """Endpoint para servir el favicon."""
        return send_from_directory(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
            "favicon.ico",
            mimetype='image/vnd.microsoft.icon'
        )

    # Manejadores de errores globales
    @app.errorhandler(404)
    def not_found_error(error):
        """Maneja errores 404 devolviendo JSON."""
        if request.path.startswith('/afip/'):
            return jsonify({"error": "Ruta no encontrada"}), 404
        return error

    @app.errorhandler(500)
    def internal_error(error):
        """Maneja errores 500 devolviendo JSON."""
        if request.path.startswith('/afip/'):
            return jsonify({"error": "Error interno del servidor"}), 500
        return error

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Maneja errores 405 devolviendo JSON."""
        if request.path.startswith('/afip/'):
            return jsonify({"error": "Método no permitido"}), 405
        return error
    
    # Configurar logging
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=1024 * 1024,  # 1MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    
    # Registrar middleware
    app.before_request(log_request_info)
    
    return app 