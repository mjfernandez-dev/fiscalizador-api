import os, base64, subprocess  # Importa módulos para manejo de archivos, codificación y ejecución de comandos externos.
from datetime import datetime, timedelta, timezone  # Importa clases para manejar fechas y horas.
from zeep import Client  # Importa la clase Client de la librería Zeep para consumir servicios SOAP.
from lxml import etree  # Se importa etree para parsear XML.

TA_CACHE_PATH = "ta.xml"  # Define la ruta del archivo de cache del TA (Ticket de Acceso).

# Definir los servicios disponibles
SERVICIOS = {
    'wsfe': 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',  # Homologación
    'ws_sr_padron_a5': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl',  # Homologación
    'ws_sr_constancia_inscripcion': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl'  # Homologación
}

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

def verificar_token_valido(ta_xml):
    """Verifica si el token es válido y no está próximo a expirar"""
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
    """Obtiene el Ticket de Acceso (TA) para el servicio especificado"""
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio no válido. Servicios disponibles: {', '.join(SERVICIOS.keys())}")
    
    try:
        # Verificar si existe y es válido
        if os.path.exists(TA_CACHE_PATH):
            with open(TA_CACHE_PATH) as f:
                ta_xml = f.read()
                if verificar_token_valido(ta_xml):
                    print("Usando token existente válido")
                    return ta_xml
                else:
                    print("Token existente expirado o próximo a expirar")
                    os.remove(TA_CACHE_PATH)
    except Exception as e:
        print(f"Error al leer token existente: {str(e)}")
        if os.path.exists(TA_CACHE_PATH):
            os.remove(TA_CACHE_PATH)

    # Generar nuevo token
    print("Generando nuevo token...")
    tra = generar_tra(servicio)
    cms_b64 = firmar_tra(tra, cert_path, key_path)

    client = Client(SERVICIOS[servicio])
    response = client.service.loginCms(cms_b64)

    # Verificar que el nuevo token sea válido
    if not verificar_token_valido(response):
        raise Exception("El token generado no es válido")

    # Guardar el nuevo token
    with open(TA_CACHE_PATH, "w") as f:
        f.write(response)
    print("Nuevo token generado y guardado")
    return response

def extraer_token_sign(ta_xml):  # Función para extraer el token y la firma del XML del TA.
    xml = etree.fromstring(ta_xml.encode())  # Se convierte la cadena XML a un árbol de elementos.
    token = xml.findtext(".//token")  # Se busca el elemento token dentro del árbol.
    sign = xml.findtext(".//sign")  # Se busca el elemento sign dentro del árbol.
    return token, sign  # Se devuelve el token y la firma.
