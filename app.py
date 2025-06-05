from flask import Flask, request, jsonify
from afip.wsaa import obtener_ta, extraer_token_sign, generar_tra, firmar_tra
from afip.wsfe import enviar_comprobante, construir_soap
from afip.wsfe_consulta import consultar_ultimo_autorizado
from afip.config import CERT, KEY, CUIT
from flask import send_from_directory
from datetime import datetime, timezone
import os
import xml.etree.ElementTree as ET
import pytz
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Configurar logging
if not app.debug:
    # Crear directorio de logs si no existe
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # Configurar el handler para archivo
    file_handler = RotatingFileHandler('logs/fiscalizador.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Configurar el handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('Fiscalizador startup')

# Filtrar logs de Flask
class RequestFilter(logging.Filter):
    def filter(self, record):
        # Ignorar solicitudes a rutas específicas
        if hasattr(record, 'msg'):
            if '/.well-known/' in str(record.msg):
                return False
            if 'favicon.ico' in str(record.msg):
                return False
        return True

# Aplicar el filtro a los handlers de Flask
for handler in app.logger.handlers:
    handler.addFilter(RequestFilter())

# También aplicar a los handlers de werkzeug
logging.getLogger('werkzeug').addFilter(RequestFilter())

def verificar_ta():
    """Verifica el estado del TA y retorna (está_válido, mensaje_error)"""
    if not os.path.exists("ta.xml"):
        return False, "El Ticket de Acceso (TA) no existe. Por favor, regenere el TA."
    
    try:
        with open("ta.xml") as f:
            ta_xml = f.read()
        
        root = ET.fromstring(ta_xml)
        exp_time = root.findtext(".//expirationTime")
        
        if not exp_time:
            return False, "El TA no tiene fecha de expiración válida. Por favor, regenere el TA."
            
        # Convertir la fecha de expiración a datetime con zona horaria
        exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
        # Obtener la fecha actual con zona horaria
        now = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
        
        if now >= exp_datetime:
            return False, f"El TA está expirado. Fecha de expiración: {exp_time}. Por favor, regenere el TA."
            
        return True, None
        
    except Exception as e:
        return False, f"Error al verificar el TA: {str(e)}"

@app.route("/fiscalizar", methods=["POST"])
def fiscalizar():
    try:
        datos = request.json
        if not datos:
            app.logger.error("No se recibieron datos en la solicitud")
            return jsonify({"error": "No se recibieron datos"}), 400

        # Verificar estado del TA
        ta_valido, mensaje_error = verificar_ta()
        if not ta_valido:
            app.logger.error(f"TA inválido: {mensaje_error}")
            return jsonify({"error": mensaje_error}), 400

        # Obtener TA
        try:
            ta_xml = obtener_ta(CERT, KEY)
            token, sign = extraer_token_sign(ta_xml)
        except Exception as e:
            app.logger.error(f"Error al obtener TA: {str(e)}")
            return jsonify({"error": f"Error al obtener el Ticket de Acceso: {str(e)}"}), 500

        # Consultar último comprobante autorizado
        try:
            pto_vta = int(datos.get('punto_venta', 12))
            cbte_tipo = int(datos.get('tipo_comprobante', 1))
            ultimo = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)
            
            if ultimo['ultimo_numero'] is None:
                siguiente_numero = 1
            else:
                siguiente_numero = ultimo['ultimo_numero'] + 1
                
            app.logger.info(f"Último número autorizado: {ultimo['ultimo_numero']}, Siguiente número a usar: {siguiente_numero}")
            
            # Si el número de comprobante ya está en los datos, verificar que sea el correcto
            if 'cbte_desde' in datos:
                cbte_desde = int(datos['cbte_desde'])
                if cbte_desde != siguiente_numero:
                    app.logger.warning(f"Número de comprobante incorrecto: {cbte_desde}, debería ser {siguiente_numero}")
                    return jsonify({
                        "error": f"El número de comprobante {cbte_desde} no es el siguiente a autorizar. El siguiente número debe ser {siguiente_numero}",
                        "ultimo_autorizado": ultimo['ultimo_numero'],
                        "siguiente_numero": siguiente_numero
                    }), 400
            
            # Agregar el número de comprobante a los datos
            datos['cbte_desde'] = siguiente_numero
            datos['cbte_hasta'] = siguiente_numero
            
        except Exception as e:
            app.logger.error(f"Error al consultar último comprobante: {str(e)}")
            return jsonify({"error": f"Error al consultar último comprobante: {str(e)}"}), 500

        # Enviar a AFIP
        try:
            app.logger.info("Enviando comprobante a AFIP...")
            app.logger.debug(f"Datos del comprobante: {datos}")
            respuesta_afip = enviar_comprobante(token, sign, CUIT, datos)
            app.logger.info("Respuesta recibida de AFIP")
            app.logger.debug(f"Respuesta AFIP: {respuesta_afip}")
        except Exception as e:
            error_msg = str(e)
            if "Error de AFIP:" in error_msg:
                app.logger.error(f"Error de AFIP: {error_msg}")
                return jsonify({"error": error_msg}), 400
            elif "Connection reset by peer" in error_msg:
                app.logger.error("Error de conexión con AFIP")
                return jsonify({"error": "Error de conexión con AFIP. Por favor, intente nuevamente en unos minutos."}), 503
            elif "timeout" in error_msg.lower():
                app.logger.error("Timeout al conectar con AFIP")
                return jsonify({"error": "Timeout al conectar con AFIP. Por favor, intente nuevamente."}), 504
            else:
                app.logger.error(f"Error al enviar comprobante: {error_msg}")
                return jsonify({"error": f"Error al enviar comprobante a AFIP: {error_msg}"}), 500

        # Intentar parsear la respuesta
        try:
            from lxml import etree
            xml_resp = etree.fromstring(respuesta_afip.encode())
            
            # Definir el namespace
            ns = {'ns': 'http://ar.gov.afip.dif.FEV1/'}
            
            # Verificar el resultado usando la ruta correcta con namespace
            resultado = xml_resp.findtext(".//ns:FeCabResp/ns:Resultado", namespaces=ns)
            app.logger.info(f"Resultado de AFIP: {resultado}")
            
            if resultado == "A":  # A = Aprobado
                # Extraer la información exitosa usando las rutas correctas con namespace
                cae = xml_resp.findtext(".//ns:FECAEDetResponse/ns:CAE", namespaces=ns)
                cae_fch_vto = xml_resp.findtext(".//ns:FECAEDetResponse/ns:CAEFchVto", namespaces=ns)
                
                app.logger.info(f"CAE: {cae}, Fecha vto: {cae_fch_vto}")
                
                if not all([cae, cae_fch_vto]):
                    app.logger.error("Respuesta de AFIP sin CAE o fecha de vencimiento")
                    return jsonify({"error": "Error de AFIP: La respuesta no contiene CAE o fecha de vencimiento"}), 500
                
                # Verificar si hay observaciones (advertencias) dentro de FECAEDetResponse
                observaciones = xml_resp.findall(".//ns:FECAEDetResponse/ns:Observaciones/ns:Obs", namespaces=ns)
                mensajes_obs = []
                if observaciones:
                    mensajes_obs = [f"{obs.findtext('ns:Code', namespaces=ns)}: {obs.findtext('ns:Msg', namespaces=ns)}" for obs in observaciones]
                    app.logger.info(f"Observaciones de AFIP: {mensajes_obs}")
                
                respuesta = {
                    "CAE": cae,
                    "CAEFchVto": cae_fch_vto,
                    "CbteNro": datos['cbte_desde'],
                    "PtoVta": datos['punto_venta'],
                    "CbteTipo": datos['tipo_comprobante'],
                    "observaciones": mensajes_obs if mensajes_obs else None
                }
                app.logger.info("Comprobante aprobado exitosamente")
                return jsonify(respuesta), 200  # Éxito
                
            elif resultado == "R":  # R = Rechazado
                # Buscar observaciones en FECAEDetResponse
                observaciones = xml_resp.findall(".//ns:FECAEDetResponse/ns:Observaciones/ns:Obs", namespaces=ns)
                if observaciones:
                    mensajes_error = [f"{obs.findtext('ns:Code', namespaces=ns)}: {obs.findtext('ns:Msg', namespaces=ns)}" for obs in observaciones]
                    app.logger.error(f"Comprobante rechazado por AFIP: {mensajes_error}")
                    return jsonify({"error": "Error de AFIP: " + " | ".join(mensajes_error)}), 400
                app.logger.error("Comprobante rechazado por AFIP sin mensaje específico")
                return jsonify({"error": "El comprobante fue rechazado por AFIP"}), 400
            else:
                app.logger.error(f"Resultado inesperado de AFIP: {resultado}")
                app.logger.debug(f"XML completo recibido: {respuesta_afip}")
                return jsonify({"error": f"Resultado inesperado de AFIP: {resultado}"}), 500
                
        except Exception as e:
            app.logger.error(f"Error al parsear respuesta XML: {str(e)}")
            return jsonify({"error": f"Error al procesar la respuesta de AFIP: {str(e)}"}), 500

    except Exception as e:
        app.logger.error(f"Error no manejado en fiscalizar: {str(e)}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

@app.route("/")
def interfaz_web():
    return send_from_directory(".", "interface.html")

@app.route("/ultimo-comprobante", methods=["GET"])
def ultimo_comprobante():
    try:
        # Obtener parámetros de la consulta
        pto_vta = request.args.get('pto_vta', type=int, default=12)
        cbte_tipo = request.args.get('cbte_tipo', type=int, default=1)
        
        # Obtener TA
        ta_xml = obtener_ta(CERT, KEY)
        token, sign = extraer_token_sign(ta_xml)
        
        # Consultar último comprobante
        resultado = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)
        
        # Construir respuesta
        respuesta = {
            "ultimo_comprobante": resultado,
            "siguiente_numero": resultado['ultimo_numero'] + 1 if resultado['ultimo_numero'] is not None else 1,
            "punto_venta": pto_vta,
            "tipo_comprobante": cbte_tipo
        }
        
        # Agregar fecha si está disponible
        if resultado.get('fecha_ultimo'):
            respuesta['fecha_ultimo'] = resultado['fecha_ultimo']
            
        return jsonify(respuesta)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/estado-ta", methods=["GET"])
def estado_ta():
    try:
        ta_valido, mensaje_error = verificar_ta()
        ta_info = {
            "valido": ta_valido,
            "mensaje": mensaje_error if not ta_valido else "El TA está vigente",
            "existe": os.path.exists("ta.xml"),
            "fecha_creacion": None,
            "fecha_expiracion": None,
            "tiempo_restante": None,
            "token": None,
            "sign": None
        }

        if ta_info["existe"]:
            # Leer el TA
            with open("ta.xml") as f:
                ta_xml = f.read()
            
            # Parsear el XML
            root = ET.fromstring(ta_xml)
            
            # Extraer fechas
            exp_time = root.findtext(".//expirationTime")
            gen_time = root.findtext(".//generationTime")
            
            if exp_time:
                ta_info["fecha_expiracion"] = exp_time
                exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
                # Obtener la fecha actual con zona horaria
                now = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
                tiempo_restante = exp_datetime - now
                ta_info["tiempo_restante"] = {
                    "dias": tiempo_restante.days,
                    "horas": tiempo_restante.seconds // 3600,
                    "minutos": (tiempo_restante.seconds % 3600) // 60
                }
            if gen_time:
                ta_info["fecha_creacion"] = gen_time

            # Extraer token y sign
            token, sign = extraer_token_sign(ta_xml)
            ta_info["token"] = token[:10] + "..." if token else None
            ta_info["sign"] = sign[:10] + "..." if sign else None

        return jsonify(ta_info)

    except Exception as e:
        return jsonify({
            "error": str(e),
            "valido": False,
            "mensaje": f"Error al verificar el estado del TA: {str(e)}"
        }), 500

@app.route("/regenerar-ta", methods=["POST"])
def regenerar_ta():
    try:
        # Eliminar TA existente si existe
        if os.path.exists("ta.xml"):
            os.remove("ta.xml")
        
        # Generar nuevo TA
        ta_xml = obtener_ta(CERT, KEY)
        token, sign = extraer_token_sign(ta_xml)
        
        return jsonify({
            "mensaje": "TA regenerado exitosamente",
            "token": token[:10] + "...",
            "sign": sign[:10] + "...",
            "fecha_generacion": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
    



