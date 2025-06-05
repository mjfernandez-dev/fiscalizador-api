import os, base64, subprocess
from datetime import datetime, timedelta
from zeep import Client

TA_CACHE_PATH = "ta.xml"

def generar_tra(servicio="wsfe"):
    """
    Genera el XML del Ticket de Requerimiento de Acceso (TRA)
    Args:
        servicio: Servicio de AFIP (por defecto "wsfe" para Facturación Electrónica)
    Returns:
        str: XML del TRA
    """
    now = datetime.now()
    return f"""<loginTicketRequest>
  <header>
    <uniqueId>{now.strftime('%y%m%d%H%M')}</uniqueId>
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
    """
    with open("tra.xml", "w") as f:
        f.write(tra_str)
    subprocess.run([
        "openssl", "cms", "-sign",
        "-in", "tra.xml",
        "-signer", cert_path,
        "-inkey", key_path,
        "-out", "tra.cms",
        "-outform", "DER", "-nodetach"
    ], check=True)
    with open("tra.cms", "rb") as f:
        return base64.b64encode(f.read()).decode()

def obtener_ta(cert_path, key_path):
    """
    Obtiene el Ticket de Acceso (TA) de AFIP
    Si existe un TA válido en caché, lo retorna
    Si no, genera uno nuevo
    Args:
        cert_path: Ruta al certificado
        key_path: Ruta a la clave privada
    Returns:
        str: XML del TA
    """
    if os.path.exists(TA_CACHE_PATH):
        with open(TA_CACHE_PATH) as f:
            return f.read()

    tra = generar_tra()
    cms_b64 = firmar_tra(tra, cert_path, key_path)
    client = Client("https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL")
    response = client.service.loginCms(cms_b64)

    with open(TA_CACHE_PATH, "w") as f:
        f.write(response)   
    return response

def extraer_token_sign(ta_xml):
    """
    Extrae el token y la firma del TA
    Args:
        ta_xml: XML del TA
    Returns:
        tuple: (token, sign)
    """
    from lxml import etree
    xml = etree.fromstring(ta_xml.encode())
    token = xml.findtext(".//token")
    sign = xml.findtext(".//sign")
    return token, sign
