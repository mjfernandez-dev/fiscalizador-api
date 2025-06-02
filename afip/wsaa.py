"""
Módulo para manejo de autenticación con ARCA.
Contiene funciones para obtener y validar tokens de acceso.
"""
import os, base64, subprocess
from datetime import datetime, timedelta, timezone
from zeep import Client
from lxml import etree

from app.config import SERVICIOS, TOKEN_FILE, CERT, KEY

def generar_tra(servicio="wsfe"):
    """Genera el XML del TRA (Ticket Request)."""
    now = datetime.now()
    return f"""<loginTicketRequest>
  <header>
    <uniqueId>{now.strftime('%y%m%d%H%M')}</uniqueId>
    <generationTime>{(now - timedelta(minutes=10)).isoformat()}</generationTime>
    <expirationTime>{(now + timedelta(minutes=10)).isoformat()}</expirationTime>
  </header>
  <service>{servicio}</service>
</loginTicketRequest>"""

def firmar_tra(tra, cert_path, key_path):
    """Firma el TRA usando OpenSSL."""
    # Crear archivo temporal para el TRA
    with open("tra.xml", "w") as f:
        f.write(tra)
    
    # Firmar el TRA
    cmd = f"openssl cms -sign -in tra.xml -out tra.cms -signer {cert_path} -inkey {key_path} -nodetach -outform PEM"
    subprocess.run(cmd, shell=True, check=True)
    
    # Leer el CMS firmado
    with open("tra.cms", "r") as f:
        cms = f.read()
    
    # Limpiar archivos temporales
    os.remove("tra.xml")
    os.remove("tra.cms")
    
    # Retornar el CMS en base64
    return base64.b64encode(cms.encode()).decode()

def extraer_token_sign(ta_xml):
    """Extrae el token y la firma del TA."""
    try:
        xml = etree.fromstring(ta_xml.encode())
        token = xml.findtext(".//token")
        sign = xml.findtext(".//sign")
        if not token or not sign:
            raise ValueError("Token o firma no encontrados en el TA")
        return token, sign
    except Exception as e:
        raise ValueError(f"Error al extraer token y firma: {str(e)}")

def verificar_token_valido(ta_xml):
    """Verifica si el token es válido y no está próximo a expirar."""
    try:
        xml = etree.fromstring(ta_xml.encode())
        exp_time = xml.findtext(".//expirationTime")
        if not exp_time:
            return False
        
        exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
        ahora_utc = datetime.now(timezone.utc)
        
        # Consideramos válido si expira en más de 5 minutos
        return ahora_utc + timedelta(minutes=5) < exp_datetime
    except Exception as e:
        print(f"Error al verificar token: {str(e)}")
        return False

def obtener_ta(cert_path, key_path, servicio='wsfe'):
    """Obtiene el Ticket de Acceso (TA) para el servicio especificado."""
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio no válido. Servicios disponibles: {', '.join(SERVICIOS.keys())}")
    
    try:
        # Verificar si existe y es válido
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as f:
                ta_xml = f.read()
                if verificar_token_valido(ta_xml):
                    print("Usando token existente válido")
                    return ta_xml
                else:
                    print("Token existente expirado o próximo a expirar")
                    os.remove(TOKEN_FILE)
    except Exception as e:
        print(f"Error al leer token existente: {str(e)}")
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)

    # Generar nuevo token
    print("Generando nuevo token...")
    tra = generar_tra(servicio)
    cms_b64 = firmar_tra(tra, cert_path, key_path)

    # Usar el servicio WSAA para autenticación
    client = Client(SERVICIOS['wsaa'])
    response = client.service.loginCms(cms_b64)

    # Verificar que el nuevo token sea válido
    if not verificar_token_valido(response):
        raise Exception("El token generado no es válido")

    # Guardar el nuevo token
    with open(TOKEN_FILE, "w") as f:
        f.write(response)
    print("Nuevo token generado y guardado")
    return response
