import os, base64, subprocess  # Importa módulos para manejo de archivos, codificación y ejecución de comandos externos.
from datetime import datetime, timedelta  # Importa clases para manejar fechas y horas.
from zeep import Client  # Importa la clase Client de la librería Zeep para consumir servicios SOAP.

TA_CACHE_PATH = "ta.xml"  # Define la ruta del archivo de cache del TA (Ticket de Acceso).

def generar_tra(servicio="wsfe"):  # Función para generar el XML del TRA (Ticket Request).
    now = datetime.now()  # Se obtiene la fecha y hora actual.
    # Se retorna una cadena de texto con el formato XML requerido por AFIP para solicitar el TA.
    # Se incluyen: uniqueId (identificador único), generationTime (fecha de generación) y expirationTime (fecha de expiración).
    # El servicio por defecto es "wsfe" (Web Service de Factura Electrónica).
    return f"""<loginTicketRequest>
  <header>
    <uniqueId>{now.strftime('%y%m%d%H%M')}</uniqueId>  <!-- Formato de fecha y hora en el identificador único. -->
    <generationTime>{(now - timedelta(minutes=10)).isoformat()}</generationTime>  <!-- Fecha de generación (10 minutos antes). -->
    <expirationTime>{(now + timedelta(minutes=10)).isoformat()}</expirationTime>  <!-- Fecha de expiración (10 minutos después). -->
  </header>
  <service>{servicio}</service>  <!-- Nombre del servicio solicitado (wsfe). -->
</loginTicketRequest>"""

def firmar_tra(tra_str, cert_path, key_path):  # Función para firmar el TRA con el certificado digital.
    with open("tra.xml", "w") as f:  # Se escribe el contenido del TRA en un archivo temporal.
        f.write(tra_str)
    subprocess.run([  # Se ejecuta OpenSSL como un proceso externo para firmar el archivo TRA.
        "openssl", "cms", "-sign",  # Comando para firmar digitalmente usando CMS (Cryptographic Message Syntax).
        "-in", "tra.xml",  # Archivo de entrada.
        "-signer", cert_path,  # Certificado firmado de la empresa.
        "-inkey", key_path,  # Clave privada para firmar.
        "-out", "tra.cms",  # Archivo de salida.
        "-outform", "DER", "-nodetach"  # Formato DER, sin separación de la firma.
    ], check=True)  # check=True lanza una excepción si el comando falla.

    with open("tra.cms", "rb") as f:  # Se lee el archivo firmado en binario.
        return base64.b64encode(f.read()).decode()  # Se convierte a Base64 y se decodifica a string.

def obtener_ta(cert_path, key_path):  # Función para obtener el Ticket de Acceso (TA).
    if os.path.exists(TA_CACHE_PATH):  # Verifica si ya existe el archivo TA.
        with open(TA_CACHE_PATH) as f:
            return f.read()  # Si existe, se lee y devuelve el TA en caché.

    tra = generar_tra()  # Se genera el TRA (Ticket Request).
    cms_b64 = firmar_tra(tra, cert_path, key_path)  # Se firma el TRA y se obtiene el resultado en Base64.

    client = Client("https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL")  # Se crea un cliente SOAP apuntando al servicio de autenticación de AFIP (entorno de homologación).
    response = client.service.loginCms(cms_b64)  # Se envía el TRA firmado y se obtiene la respuesta del servicio.

    with open(TA_CACHE_PATH, "w") as f:  # Se guarda el TA en el archivo para usarlo luego sin necesidad de solicitarlo de nuevo.
        f.write(response)
    return response  # Se devuelve el TA.

def extraer_token_sign(ta_xml):  # Función para extraer el token y la firma del XML del TA.
    from lxml import etree  # Se importa etree para parsear XML.
    xml = etree.fromstring(ta_xml.encode())  # Se convierte la cadena XML a un árbol de elementos.
    token = xml.findtext(".//token")  # Se busca el elemento token dentro del árbol.
    sign = xml.findtext(".//sign")  # Se busca el elemento sign dentro del árbol.
    return token, sign  # Se devuelve el token y la firma.
