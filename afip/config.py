import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Obtener credenciales desde variables de entorno
CERT = os.getenv('AFIP_CERT_PATH')
KEY = os.getenv('AFIP_KEY_PATH')
CUIT = os.getenv('AFIP_CUIT')

# Validar que las credenciales existan
if not all([CERT, KEY, CUIT]):
    raise ValueError("Faltan credenciales de AFIP en el archivo .env")

# Validar que los archivos existan
if not os.path.exists(CERT):
    raise ValueError(f"El certificado no existe en la ruta: {CERT}")
if not os.path.exists(KEY):
    raise ValueError(f"La clave privada no existe en la ruta: {KEY}")

# Validar formato de CUIT
if not CUIT.isdigit() or len(CUIT) != 11:
    raise ValueError("La CUIT debe ser un número de 11 dígitos")

# Configuración de seguridad
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8080').split(',')
API_KEY = os.getenv('API_KEY')  # Para autenticación de API
TOKEN_EXPIRY_MINUTES = int(os.getenv('TOKEN_EXPIRY_MINUTES', '10'))
MAX_REQUESTS_PER_MINUTE = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '60'))
