"""
Punto de entrada principal de la aplicación.
"""
import os
from app import create_app

# Crear la aplicación Flask
app = create_app(os.getenv('FLASK_ENV', 'default'))

if __name__ == "__main__":
    # Iniciar servidor con SSL en producción
    if os.getenv('FLASK_ENV') == 'production':
        ssl_context = (
            os.getenv('SSL_CERT_PATH'),
            os.getenv('SSL_KEY_PATH')
        )
        app.run(
            host="0.0.0.0", 
            port=8443,  # Puerto HTTPS estándar
            ssl_context=ssl_context,
            threaded=True
        )
    else:
        app.run(host="0.0.0.0", port=8080)
