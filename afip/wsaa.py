"""
Módulo para manejo de autenticación con ARCA.
Contiene funciones para obtener y validar tokens de acceso.
"""
import os
import base64
import subprocess
import time
import logging
from datetime import datetime, timedelta, timezone
from zeep import Client
from lxml import etree

from app.config import SERVICIOS, CERT, KEY

# Configurar logging
logger = logging.getLogger(__name__)

# Crear directorio tokens si no existe
TOKENS_DIR = "tokens"
if not os.path.exists(TOKENS_DIR):
    os.makedirs(TOKENS_DIR)
    logger.info(f"Directorio {TOKENS_DIR} creado")

# Rutas de los archivos de autenticación
TA_CACHE_PATH = os.path.join(TOKENS_DIR, "ta.xml")
TRA_XML_PATH = os.path.join(TOKENS_DIR, "tra.xml")
TRA_CMS_PATH = os.path.join(TOKENS_DIR, "tra.cms")

def limpiar_archivos_temporales():
    """Limpia los archivos temporales de autenticación."""
    for archivo in [TRA_XML_PATH, TRA_CMS_PATH]:
        try:
            if os.path.exists(archivo):
                os.remove(archivo)
                logger.debug(f"Archivo temporal {archivo} eliminado")
        except Exception as e:
            logger.warning(f"Error al eliminar archivo temporal {archivo}: {str(e)}")

def generar_tra(servicio="wsfe"):
    """
    Genera el XML del Ticket de Requerimiento de Acceso (TRA)
    Args:
        servicio: Servicio de AFIP (por defecto "wsfe" para Facturación Electrónica)
    Returns:
        str: XML del TRA
    """
    # Generar un ID único usando timestamp con microsegundos
    now = datetime.now()
    unique_id = now.strftime('%y%m%d%H%M%S%f')[:14]  # Tomamos solo los primeros 14 dígitos
    
    return f"""<loginTicketRequest>
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{(now - timedelta(minutes=10)).isoformat()}</generationTime>
    <expirationTime>{(now + timedelta(minutes=10)).isoformat()}</expirationTime>
  </header>
  <service>{servicio}</service>
</loginTicketRequest>"""

def firmar_tra(tra_str, cert_path, key_path):
    """
    Firma el TRA usando OpenSSL
    Args:
        tra_str: XML del TRA a firmar
        cert_path: Ruta al certificado
        key_path: Ruta a la clave privada
    Returns:
        str: TRA firmado en base64
    Raises:
        FileNotFoundError: Si no se encuentra el certificado o la clave
        subprocess.CalledProcessError: Si falla el comando OpenSSL
        Exception: Para otros errores
    """
    try:
        # Verificar que existan los archivos necesarios
        if not os.path.exists(cert_path):
            raise FileNotFoundError(f"No se encuentra el certificado en {cert_path}")
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"No se encuentra la clave privada en {key_path}")

        # Limpiar archivos temporales anteriores
        limpiar_archivos_temporales()
        
        # Guardar TRA en archivo temporal
        with open(TRA_XML_PATH, "w") as f:
            f.write(tra_str)
        logger.debug(f"TRA guardado en {TRA_XML_PATH}")
        
        # Firmar usando OpenSSL CMS
        try:
            subprocess.run([
                "openssl", "cms", "-sign",
                "-in", TRA_XML_PATH,
                "-signer", cert_path,
                "-inkey", key_path,
                "-out", TRA_CMS_PATH,
                "-outform", "DER", "-nodetach"
            ], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error al firmar con OpenSSL: {e.stderr}")
        
        # Leer el archivo firmado y codificarlo en base64
        with open(TRA_CMS_PATH, "rb") as f:
            cms_content = f.read()
            return base64.b64encode(cms_content).decode()
            
    except Exception as e:
        logger.error(f"Error al firmar TRA: {str(e)}")
        raise

def extraer_token_sign(ta_xml):
    """
    Extrae el token y la firma del TA.
    Args:
        ta_xml: XML del Ticket de Acceso
    Returns:
        tuple: (token, sign)
    Raises:
        ValueError: Si no se encuentran el token o la firma
    """
    try:
        xml = etree.fromstring(ta_xml.encode())
        token = xml.findtext(".//token")
        sign = xml.findtext(".//sign")
        if not token or not sign:
            raise ValueError("Token o firma no encontrados en el TA")
        return token, sign
    except Exception as e:
        logger.error(f"Error al extraer token y firma: {str(e)}")
        raise ValueError(f"Error al extraer token y firma: {str(e)}")

def verificar_token_valido(ta_xml):
    """
    Verifica si el token es válido y no está próximo a expirar.
    Args:
        ta_xml: XML del Ticket de Acceso
    Returns:
        tuple: (bool, str) - (es_válido, mensaje)
    """
    try:
        xml = etree.fromstring(ta_xml.encode())
        
        # Verificar que el XML tenga la estructura esperada
        if xml.tag != "loginTicketResponse":
            return False, "Estructura de XML inválida: no es un loginTicketResponse"
            
        # Obtener y validar el tiempo de expiración
        exp_time = xml.findtext(".//expirationTime")
        if not exp_time:
            return False, "No se encontró tiempo de expiración en el token"
        
        try:
            exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
        except ValueError as e:
            return False, f"Formato de fecha inválido en el token: {str(e)}"
            
        ahora_utc = datetime.now(timezone.utc)
        
        # Calcular tiempo restante
        tiempo_restante = exp_datetime - ahora_utc
        minutos_restantes = tiempo_restante.total_seconds() / 60
        
        # Consideramos válido si expira en más de 5 minutos
        if minutos_restantes > 5:
            return True, f"Token válido. Expira en {int(minutos_restantes)} minutos"
            
        if minutos_restantes > 0:
            return False, f"Token próximo a expirar. Quedan {int(minutos_restantes)} minutos"
            
        return False, "Token expirado"
        
    except etree.XMLSyntaxError as e:
        return False, f"Error de sintaxis XML en el token: {str(e)}"
    except Exception as e:
        return False, f"Error al verificar token: {str(e)}"

def obtener_ta(cert_path, key_path, servicio='wsfe'):
    """
    Obtiene el Ticket de Acceso (TA) para el servicio especificado.
    Args:
        cert_path: Ruta al certificado
        key_path: Ruta a la clave privada
        servicio: Servicio de AFIP (por defecto "wsfe" para Facturación Electrónica)
    Returns:
        str: XML del TA
    Raises:
        ValueError: Si el servicio no es válido
        Exception: Para otros errores
    """
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio no válido. Servicios disponibles: {', '.join(SERVICIOS.keys())}")
    
    # Verificar si existe el archivo ta.xml
    if not os.path.exists(TA_CACHE_PATH):
        logger.info(f"No se encontró archivo de token en {TA_CACHE_PATH}")
        logger.info("Se generará un nuevo token...")
    else:
        try:
            logger.info(f"Verificando token existente en {TA_CACHE_PATH}")
            with open(TA_CACHE_PATH) as f:
                ta_xml = f.read()
                es_valido, mensaje = verificar_token_valido(ta_xml)
                logger.info(f"Estado del token: {mensaje}")
                if es_valido:
                    return ta_xml
                else:
                    logger.info(f"Token no válido, será regenerado: {mensaje}")
                    os.remove(TA_CACHE_PATH)
        except Exception as e:
            logger.error(f"Error al verificar token existente: {str(e)}")
            if os.path.exists(TA_CACHE_PATH):
                os.remove(TA_CACHE_PATH)

    # Generar nuevo token
    logger.info("Iniciando generación de nuevo token...")
    max_intentos = 3
    intento = 0
    
    while intento < max_intentos:
        try:
            logger.info(f"Intento {intento + 1} de {max_intentos}")
            # Generar un nuevo TRA con ID único para cada intento
            tra = generar_tra(servicio)
            cms_b64 = firmar_tra(tra, cert_path, key_path)

            # Usar el servicio WSAA para autenticación
            logger.info("Enviando solicitud a AFIP...")
            client = Client(SERVICIOS['wsaa'])
            response = client.service.loginCms(cms_b64)

            # Verificar que el nuevo token sea válido
            es_valido, mensaje = verificar_token_valido(response)
            if not es_valido:
                raise Exception(f"El token generado no es válido: {mensaje}")

            # Guardar el nuevo token
            logger.info(f"Guardando nuevo token en {TA_CACHE_PATH}")
            with open(TA_CACHE_PATH, "w") as f:
                f.write(response)
            logger.info("Nuevo token generado y guardado exitosamente")
            
            # Limpiar archivos temporales
            limpiar_archivos_temporales()
            
            return response

        except Exception as e:
            error_msg = str(e)
            if "ya posee un TA valido" in error_msg:
                logger.warning(f"Intento {intento + 1}: AFIP indica que ya existe un TA válido")
                # Esperamos un momento antes de reintentar
                time.sleep(1)
                intento += 1
                continue
            logger.error(f"Error al obtener token AFIP: {error_msg}")
            raise Exception(f"Error al obtener token AFIP: {error_msg}")
    
    raise Exception("No se pudo obtener un token válido después de varios intentos")
