from flask import Flask, request, jsonify
from afip.wsaa import obtener_ta, extraer_token_sign, generar_tra, firmar_tra
from afip.wsfe import enviar_comprobante, construir_xml_comprobante 
from afip.wsfe_consulta import consultar_ultimo_autorizado
from afip.config import CERT, KEY, CUIT
from flask import send_from_directory
from datetime import datetime
import os
import xml.etree.ElementTree as ET

app = Flask(__name__)

@app.route("/fiscalizar", methods=["POST"])
def fiscalizar():
    try:
        datos = request.json
        if not datos:
            return jsonify({"error": "No se recibieron datos"}), 400

        # Obtener TA
        ta_xml = obtener_ta(CERT, KEY)
        token, sign = extraer_token_sign(ta_xml)

        # Consultar último comprobante autorizado
        pto_vta = int(datos.get('punto_venta', 12))
        cbte_tipo = int(datos.get('tipo_comprobante', 1))
        ultimo = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)
        siguiente_numero = ultimo['ultimo_numero'] + 1 if ultimo['ultimo_numero'] is not None else 1

        # Agregar el número de comprobante a los datos
        datos['cbte_desde'] = siguiente_numero
        datos['cbte_hasta'] = siguiente_numero

        # Construir el XML del comprobante
        try:
            datos_cbte_xml = construir_xml_comprobante(datos)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Enviar a AFIP
        respuesta_afip = enviar_comprobante(token, sign, CUIT, datos_cbte_xml)
        
        # Intentar parsear la respuesta para ver si hay errores
        try:
            from lxml import etree
            xml_resp = etree.fromstring(respuesta_afip.encode())
            errores = xml_resp.findall(".//Err")
            if errores:
                mensajes_error = [f"{err.findtext('Code')}: {err.findtext('Msg')}" for err in errores]
                return jsonify({"error": "Error de AFIP: " + " | ".join(mensajes_error)}), 400
        except:
            pass  # Si no se puede parsear, devolver la respuesta tal cual

        return respuesta_afip

    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

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
        # Verificar si existe el archivo TA
        ta_existe = os.path.exists("ta.xml")
        ta_info = {
            "existe": ta_existe,
            "fecha_creacion": None,
            "fecha_expiracion": None,
            "token": None,
            "sign": None
        }

        if ta_existe:
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
            if gen_time:
                ta_info["fecha_creacion"] = gen_time

            # Extraer token y sign
            token, sign = extraer_token_sign(ta_xml)
            ta_info["token"] = token[:10] + "..." if token else None
            ta_info["sign"] = sign[:10] + "..." if sign else None

            # Verificar si está expirado
            if exp_time:
                exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
                ta_info["expirado"] = datetime.now() >= exp_datetime
            else:
                ta_info["expirado"] = True

        return jsonify(ta_info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    



