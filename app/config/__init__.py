"""
Configuración principal de la aplicación.
Contiene todas las constantes y configuraciones necesarias.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de AFIP/ARCA
AFIP_CERT = os.getenv('AFIP_CERT_PATH')
AFIP_KEY = os.getenv('AFIP_KEY_PATH')
AFIP_CUIT = os.getenv('AFIP_CUIT')

# Servicios web de AFIP
AFIP_SERVICIOS = {
    'wsaa': 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl',
    'wsfe': 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
    'ws_sr_padron_a5': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl',
    'ws_sr_constancia_inscripcion': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl'
}

# Validar credenciales de AFIP
if not all([AFIP_CERT, AFIP_KEY, AFIP_CUIT]):
    raise ValueError("Faltan credenciales de AFIP en el archivo .env")

# Validar archivos de AFIP
if not os.path.exists(AFIP_CERT):
    raise ValueError(f"El certificado de AFIP no existe en la ruta: {AFIP_CERT}")
if not os.path.exists(AFIP_KEY):
    raise ValueError(f"La clave privada de AFIP no existe en la ruta: {AFIP_KEY}")

# Validar formato de CUIT de AFIP
if not AFIP_CUIT.isdigit() or len(AFIP_CUIT) != 11:
    raise ValueError("La CUIT de AFIP debe ser un número de 11 dígitos")

# Configuración de seguridad
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("La API_KEY es requerida en el archivo .env")

TOKEN_EXPIRY_MINUTES = int(os.getenv('TOKEN_EXPIRY_MINUTES', '60'))
MAX_REQUESTS_PER_MINUTE = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '60'))

# Configuración de CORS
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')

# Configuración de archivos
TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tokens")
TOKEN_FILE = os.path.join(TOKEN_DIR, "ta.xml")

# Configuración de Flask
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=TOKEN_EXPIRY_MINUTES)

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SSL_CERT_PATH = os.getenv('SSL_CERT_PATH')
    SSL_KEY_PATH = os.getenv('SSL_KEY_PATH')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Exportar variables para compatibilidad con módulos existentes
CERT = AFIP_CERT
KEY = AFIP_KEY
CUIT = AFIP_CUIT
SERVICIOS = AFIP_SERVICIOS  # Para compatibilidad con código existente 