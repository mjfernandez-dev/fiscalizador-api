import os, base64, subprocess
from datetime import datetime, timedelta
from zeep import Client

TA_CACHE_PATH = "ta.xml"

def generar_tra(servicio="wsfe"):
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
    from lxml import etree
    xml = etree.fromstring(ta_xml.encode())
    token = xml.findtext(".//token")
    sign = xml.findtext(".//sign")
    return token, sign
