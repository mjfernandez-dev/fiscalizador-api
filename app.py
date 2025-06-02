from flask import Flask, request, jsonify, send_from_directory  # Importa el microframework Flask y funciones auxiliares para manejar solicitudes y servir archivos.
from afip.wsaa import obtener_ta, extraer_token_sign, generar_tra, firmar_tra  # Importa funciones para autenticación con AFIP (WSAA).
from afip.wsfe import enviar_comprobante, construir_xml_comprobante, validar_cuit_receptor  # Importa funciones para construir y enviar comprobantes electrónicos.
from afip.wsfe_consulta import consultar_ultimo_autorizado  # Importa la función para consultar el último comprobante autorizado por AFIP.
from afip.config import CERT, KEY, CUIT, ALLOWED_ORIGINS, API_KEY, TOKEN_EXPIRY_MINUTES, MAX_REQUESTS_PER_MINUTE  # Importa constantes de configuración como el certificado, clave y CUIT de la empresa.
from datetime import datetime, timedelta, timezone  # Importa la clase datetime para trabajar con fechas y horas y el módulo timezone para manejar zonas horarias.
import os  # Importa el módulo os para interactuar con el sistema de archivos.
import xml.etree.ElementTree as ET  # Importa el módulo para parsear y manipular XML.
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import hashlib
import hmac
import time

app = Flask(__name__)  # Se crea una instancia de la aplicación Flask.

# Configurar CORS con orígenes permitidos
CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "X-API-Key"]
    }
})

# Configurar rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{MAX_REQUESTS_PER_MINUTE} per minute"]
)

# Middleware para validar API key
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or not hmac.compare_digest(api_key, API_KEY):
            return jsonify({"error": "API key inválida"}), 401
        return f(*args, **kwargs)
    return decorated

# Middleware para logging de seguridad
@app.before_request
def log_request_info():
    if request.path != '/':  # No loguear peticiones a la interfaz web
        app.logger.info(
            f"Request: {request.method} {request.path} "
            f"from {request.remote_addr} "
            f"with headers {dict(request.headers)}"
        )

# Middleware para sanitización de datos
def sanitize_input(data):
    if isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, str):
        # Eliminar caracteres potencialmente peligrosos
        return ''.join(c for c in data if c.isprintable())
    return data

# Función para validar datos de entrada
def validate_input_data(data):
    required_fields = ['tipo_comprobante', 'doc_tipo', 'doc_nro', 'imp_neto']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Campo requerido faltante: {field}")
    
    # Validar tipos de datos
    if not isinstance(data.get('tipo_comprobante'), (int, str)) or \
       not isinstance(data.get('doc_tipo'), (int, str)) or \
       not isinstance(data.get('doc_nro'), (int, str)):
        raise ValueError("Los campos tipo_comprobante, doc_tipo y doc_nro deben ser números")
    
    # Validar importes
    try:
        float(data.get('imp_neto', '0'))
    except ValueError:
        raise ValueError("El importe neto debe ser un número válido")

# Definimos la ruta donde se guardarán los tokens
TOKEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens")
TOKEN_FILE = os.path.join(TOKEN_DIR, "ta.xml")

# Aseguramos que el directorio existe
os.makedirs(TOKEN_DIR, exist_ok=True)

def obtener_fecha_actual_utc():
    """Obtiene la fecha actual en UTC para comparar con el token de AFIP"""
    return datetime.now(timezone.utc)

@app.route("/fiscalizar", methods=["POST"])  # Definimos una ruta web que solo acepta peticiones POST (cuando se envía un formulario)
@require_api_key
@limiter.limit("30 per minute")  # Límite específico para este endpoint
def fiscalizar():  # Definimos la función que manejará la petición
    try:  # Usamos try/except para capturar cualquier error que pueda ocurrir
        # Sanitizar y validar datos de entrada
        datos = sanitize_input(request.json)
        if not datos:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        validate_input_data(datos)

        print("Datos recibidos:", datos)  # Mostramos en la consola del servidor qué datos recibimos (para debug)

        # Validar CUIT del receptor si es tipo 80 (CUIT)
        if datos.get('doc_tipo') == 80 and datos.get('doc_nro'):
            try:
                # Obtener token específico para Padrón A5
                ta_xml_padron = obtener_ta(CERT, KEY, servicio='ws_sr_padron_a5')
                token_padron, sign_padron = extraer_token_sign(ta_xml_padron)
                validar_cuit_receptor(token_padron, sign_padron, datos['doc_nro'])
                print(f"CUIT {datos['doc_nro']} validada correctamente")
            except ValueError as e:
                print(f"Error al validar CUIT: {str(e)}")
                return jsonify({"error": str(e)}), 400

        # Obtener token para WSFE
        ta_existe = os.path.exists(TOKEN_FILE)
        print("TA existe:", ta_existe)

        token_valido = False
        if ta_existe:
            try:
                with open(TOKEN_FILE) as f:
                    ta_xml = f.read()
                root = ET.fromstring(ta_xml)
                exp_time = root.findtext(".//expirationTime")
                if exp_time:
                    # Convertimos la fecha del token a UTC
                    exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
                    # Obtenemos la fecha actual en UTC
                    ahora_utc = obtener_fecha_actual_utc()
                    # Verificamos si el token expira en menos de 5 minutos
                    if ahora_utc + timedelta(minutes=5) < exp_datetime:
                        token_valido = True
                        print(f"Token válido, expira en: {exp_datetime} (UTC)")
                    else:
                        print(f"Token próximo a expirar o expirado. Ahora: {ahora_utc} (UTC), Expira: {exp_datetime} (UTC)")
                else:
                    print("Token sin fecha de expiración, regenerando...")
            except Exception as e:
                print("Error al verificar token:", str(e))

        if not token_valido:
            print("Generando nuevo token para WSFE...")
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            ta_xml = obtener_ta(CERT, KEY, servicio='wsfe')
            # Guardamos el nuevo token inmediatamente
            with open(TOKEN_FILE, "w") as f:
                f.write(ta_xml)
            print("Nuevo token WSFE generado y guardado")

        token, sign = extraer_token_sign(ta_xml)
        print("Token y sign WSFE obtenidos")

        # Consultar último comprobante autorizado
        pto_vta = int(datos.get('punto_venta', 12))  # Convertimos el punto de venta a número (si no viene, usamos 12)
        cbte_tipo = int(datos.get('tipo_comprobante', 1))  # Convertimos el tipo de comprobante a número (si no viene, usamos 1)
        print(f"Consultando último comprobante - PtoVta: {pto_vta}, Tipo: {cbte_tipo}")  # Mostramos qué vamos a consultar

        ultimo = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)  # Le preguntamos a AFIP cuál fue el último comprobante que autorizó
        print("Último comprobante:", ultimo)  # Mostramos la respuesta de AFIP

        siguiente_numero = ultimo['ultimo_numero'] + 1 if ultimo['ultimo_numero'] is not None else 1  # Calculamos el siguiente número sumando 1 al último, o usamos 1 si no hay comprobantes
        print(f"Siguiente número: {siguiente_numero}")  # Mostramos el número que vamos a usar

        # Agregar el número de comprobante a los datos
        datos['cbte_desde'] = siguiente_numero  # Guardamos el número inicial del comprobante
        datos['cbte_hasta'] = siguiente_numero  # Guardamos el número final (igual al inicial porque es un solo comprobante)
        print("Datos con número de comprobante:", datos)  # Mostramos los datos actualizados

        # Construir el XML del comprobante
        try:
            print("Intentando construir XML...")  # Avisamos que vamos a crear el XML
            datos_cbte_xml = construir_xml_comprobante(datos)  # Convertimos los datos en un XML que AFIP entienda
            print("XML construido:", datos_cbte_xml)  # Mostramos el XML generado
        except ValueError as e:  # Si hay algún error al crear el XML (datos faltantes, etc)
            print("Error al construir XML:", str(e))  # Mostramos el error específico
            return jsonify({"error": str(e)}), 400  # Le decimos al navegador que hubo un error (código 400)

        # Enviar a AFIP
        print("Enviando a AFIP...")  # Avisamos que vamos a enviar el comprobante
        respuesta_afip = enviar_comprobante(token, sign, CUIT, datos_cbte_xml)  # Enviamos el XML a AFIP y esperamos su respuesta
        print("Respuesta AFIP:", respuesta_afip)  # Mostramos qué nos respondió AFIP

        # Intentar parsear la respuesta para ver si hay errores
        try:
            from lxml import etree  # Importamos la herramienta para procesar XML
            xml_resp = etree.fromstring(respuesta_afip.encode())  # Convertimos la respuesta en un árbol XML
            errores = xml_resp.findall(".//Err")  # Buscamos en el árbol si hay etiquetas de error
            if errores:  # Si encontramos errores
                mensajes_error = [f"{err.findtext('Code')}: {err.findtext('Msg')}" for err in errores]  # Extraemos los códigos y mensajes de error
                print("Errores AFIP:", mensajes_error)  # Mostramos los errores encontrados
                return jsonify({"error": "Error de AFIP: " + " | ".join(mensajes_error)}), 400  # Le decimos al navegador que AFIP rechazó el comprobante
        except Exception as e:  # Si hay error al procesar la respuesta
            print("Error al parsear respuesta:", str(e))  # Mostramos el error específico
            pass  # Continuamos con la ejecución (podría ser una respuesta exitosa en formato diferente)

        return jsonify({"xml_afip": respuesta_afip})  # Si todo salió bien, le devolvemos al navegador la respuesta de AFIP

    except ValueError as e:
        app.logger.warning(f"Error de validación: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error interno: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500  # Le decimos al navegador que hubo un error interno (código 500)

@app.route("/")  # Se define la ruta raíz ("/") que sirve la interfaz web.
def interfaz_web():
    return send_from_directory(".", "interface.html")  # Se devuelve el archivo interface.html desde el directorio actual. 

@app.route("/ultimo-comprobante", methods=["GET"])  # Se define una ruta para consultar el último comprobante autorizado.
@require_api_key
@limiter.limit("60 per minute")
def ultimo_comprobante():
    try:
        # Obtener parámetros de la consulta
        pto_vta = request.args.get('pto_vta', type=int, default=12)  # Se obtiene el parámetro pto_vta de la URL o se asigna 12.
        cbte_tipo = request.args.get('cbte_tipo', type=int, default=1)  # Se obtiene el parámetro cbte_tipo de la URL o se asigna 1.

        # Obtener TA
        ta_xml = obtener_ta(CERT, KEY)  # Se obtiene el Ticket de Autenticación (TA).
        token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma digital.

        # Consultar último comprobante
        resultado = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)  # Se consulta en AFIP el último comprobante autorizado.

        # Construir respuesta
        respuesta = {
            "ultimo_comprobante": resultado,  # Se incluye la respuesta completa de AFIP.
            "siguiente_numero": resultado['ultimo_numero'] + 1 if resultado['ultimo_numero'] is not None else 1,  # Se calcula el próximo número de comprobante.
            "punto_venta": pto_vta,
            "tipo_comprobante": cbte_tipo
        }

        # Agregar fecha si está disponible
        if resultado.get('fecha_ultimo'):  # Si la fecha del último comprobante está disponible:
            respuesta['fecha_ultimo'] = resultado['fecha_ultimo']  # Se agrega la fecha a la respuesta.

        return jsonify(respuesta)  # Se devuelve la respuesta como JSON.

    except Exception as e:
        app.logger.error(f"Error en último comprobante: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500  # Se devuelve un error 500 en caso de error interno.

@app.route("/estado-ta", methods=["GET"])  # Se define una ruta para consultar el estado del TA (token de autorización).
@require_api_key
@limiter.limit("30 per minute")
def estado_ta():
    try:
        # Verificar si existe el archivo TA
        ta_existe = os.path.exists(TOKEN_FILE)  # Se verifica si el archivo ta.xml existe.
        ta_info = {  # Se crea un diccionario con la información a devolver.
            "existe": ta_existe,
            "fecha_creacion": None,
            "fecha_expiracion": None,
            "token": None,
            "sign": None
        }

        if ta_existe:  # Si el archivo existe:
            # Leer el TA
            with open(TOKEN_FILE) as f:  # Se abre y lee el archivo.
                ta_xml = f.read()

            # Parsear el XML
            root = ET.fromstring(ta_xml)  # Se convierte el XML en un árbol de elementos.

            # Extraer fechas
            exp_time = root.findtext(".//expirationTime")  # Se busca la fecha de expiración.
            gen_time = root.findtext(".//generationTime")  # Se busca la fecha de generación.

            if exp_time:
                ta_info["fecha_expiracion"] = exp_time  # Se guarda la fecha de expiración.
            if gen_time:
                ta_info["fecha_creacion"] = gen_time  # Se guarda la fecha de creación.

            # Extraer token y sign
            token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma.
            ta_info["token"] = token[:10] + "..." if token else None  # Se muestra una parte del token para seguridad.
            ta_info["sign"] = sign[:10] + "..." if sign else None  # Se muestra una parte del sign para seguridad.

            # Verificar si está expirado
            if exp_time:
                exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))  # Se convierte la fecha a objeto datetime.
                ta_info["expirado"] = obtener_fecha_actual_utc() >= exp_datetime  # Se determina si el TA está expirado.
            else:
                ta_info["expirado"] = True  # Si no hay fecha, se asume que está expirado.

        return jsonify(ta_info)  # Se devuelve la información como JSON.

    except Exception as e:
        app.logger.error(f"Error en estado TA: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500  # Se devuelve un error 500 en caso de error interno.

@app.route("/regenerar-ta", methods=["POST"])  # Se define una ruta para regenerar el TA manualmente.
@require_api_key
@limiter.limit("5 per minute")  # Límite más estricto para regeneración de token
def regenerar_ta():
    try:
        # Eliminar TA existente si existe
        if os.path.exists(TOKEN_FILE):  # Se verifica si el archivo ta.xml existe.
            os.remove(TOKEN_FILE)  # Se elimina el archivo.

        # Generar nuevo TA
        ta_xml = obtener_ta(CERT, KEY)  # Se genera un nuevo TA.
        token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma.

        # Guardamos el nuevo token en la ubicación específica
        with open(TOKEN_FILE, "w") as f:
            f.write(ta_xml)

        return jsonify({  # Se devuelve la información como JSON.
            "mensaje": "TA regenerado exitosamente",
            "token": token[:10] + "...",  # Se muestra parte del token.
            "sign": sign[:10] + "...",  # Se muestra parte del sign.
            "fecha_generacion": datetime.now().isoformat()  # Se muestra la fecha de generación.
        })

    except Exception as e:
        app.logger.error(f"Error al regenerar TA: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500  # Se devuelve un error 500 en caso de error interno.

# Configuración de logging
import logging
from logging.handlers import RotatingFileHandler

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

if __name__ == "__main__":  # Bloque de inicio para ejecutar la aplicación si se ejecuta como script principal.
    # Configuración de seguridad de Flask
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=TOKEN_EXPIRY_MINUTES)
    )
    
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
        app.run(host="0.0.0.0", port=8080)  # Se inicia el servidor Flask en todas las interfaces de red (0.0.0.0) en el puerto 8080.
