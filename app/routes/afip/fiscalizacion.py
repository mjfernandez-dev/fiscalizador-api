
"""
Rutas para fiscalización de comprobantes.
Contiene los endpoints para fiscalizar, consultar y manejar tokens.
"""
from flask import request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import xml.etree.ElementTree as ET
from lxml import etree
from datetime import datetime

from app.middleware import require_api_key, sanitize_input, validate_input_data
from app.utils.afip_utils import (
    obtener_token_afip, validar_cuit_y_obtener_token,
    consultar_ultimo_comprobante, obtener_fecha_actual_utc
)
from afip.wsfe import enviar_comprobante, construir_xml_comprobante, extraer_token_sign
from app.config import TOKEN_FILE, CUIT
import os
import logging

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address)

@require_api_key
@limiter.limit("30 per minute")
def fiscalizar():
    """Endpoint para fiscalizar comprobantes electrónicos."""
    try:
        datos = sanitize_input(request.json)
        if not datos:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        validate_input_data(datos)
        logging.info(f"Datos recibidos: {datos}")

        # Validar CUIT si es necesario
        if datos.get('doc_tipo') == 80 and datos.get('doc_nro'):
            try:
                validar_cuit_y_obtener_token(datos['doc_nro'])
                logging.info(f"CUIT {datos['doc_nro']} validada correctamente")
            except ValueError as e:
                logging.error(f"Error al validar CUIT: {str(e)}")
                return jsonify({"error": str(e)}), 400

        # Obtener token y consultar último comprobante
        token, sign = obtener_token_afip()
        pto_vta = int(datos.get('punto_venta', 12))
        cbte_tipo = int(datos.get('tipo_comprobante', 1))
        
        ultimo = consultar_ultimo_comprobante(pto_vta, cbte_tipo)
        siguiente_numero = ultimo['ultimo_numero'] + 1 if ultimo['ultimo_numero'] is not None else 1
        
        datos['cbte_desde'] = siguiente_numero
        datos['cbte_hasta'] = siguiente_numero

        # Construir y enviar comprobante
        try:
            datos_cbte_xml = construir_xml_comprobante(datos)
            respuesta_afip = enviar_comprobante(token, sign, CUIT, datos_cbte_xml)
            
            # Verificar errores en la respuesta
            xml_resp = etree.fromstring(respuesta_afip.encode())
            errores = xml_resp.findall(".//Err")
            if errores:
                mensajes_error = [f"{err.findtext('Code')}: {err.findtext('Msg')}" for err in errores]
                return jsonify({"error": "Error de AFIP: " + " | ".join(mensajes_error)}), 400

            return jsonify({"xml_afip": respuesta_afip})

        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    except ValueError as e:
        logging.warning(f"Error de validación: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error interno: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

@require_api_key
@limiter.limit("60 per minute")
def ultimo_comprobante():
    """Endpoint para consultar el último comprobante autorizado."""
    try:
        pto_vta = request.args.get('pto_vta', type=int, default=12)
        cbte_tipo = request.args.get('cbte_tipo', type=int, default=1)

        resultado = consultar_ultimo_comprobante(pto_vta, cbte_tipo)
        
        respuesta = {
            "ultimo_comprobante": resultado,
            "siguiente_numero": resultado['ultimo_numero'] + 1 if resultado['ultimo_numero'] is not None else 1,
            "punto_venta": pto_vta,
            "tipo_comprobante": cbte_tipo
        }

        if resultado.get('fecha_ultimo'):
            respuesta['fecha_ultimo'] = resultado['fecha_ultimo']

        return jsonify(respuesta)

    except Exception as e:
        logging.error(f"Error en último comprobante: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

@require_api_key
@limiter.limit("30 per minute")
def estado_ta():
    """Endpoint para consultar el estado del token de autorización."""
    try:
        ta_existe = os.path.exists(TOKEN_FILE)
        ta_info = {
            "existe": ta_existe,
            "fecha_creacion": None,
            "fecha_expiracion": None,
            "token": None,
            "sign": None
        }

        if ta_existe:
            with open(TOKEN_FILE) as f:
                ta_xml = f.read()

            root = ET.fromstring(ta_xml)
            exp_time = root.findtext(".//expirationTime")
            gen_time = root.findtext(".//generationTime")

            if exp_time:
                ta_info["fecha_expiracion"] = exp_time
                exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))
                ta_info["expirado"] = obtener_fecha_actual_utc() >= exp_datetime
            else:
                ta_info["expirado"] = True

            if gen_time:
                ta_info["fecha_creacion"] = gen_time

            token, sign = extraer_token_sign(ta_xml)
            ta_info["token"] = token[:10] + "..." if token else None
            ta_info["sign"] = sign[:10] + "..." if sign else None

        return jsonify(ta_info)

    except Exception as e:
        logging.error(f"Error en estado TA: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

@require_api_key
@limiter.limit("5 per minute")
def regenerar_ta():
    """Endpoint para regenerar manualmente el token de autorización."""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)

        token, sign = obtener_token_afip()

        return jsonify({
            "mensaje": "TA regenerado exitosamente",
            "token": token[:10] + "...",
            "sign": sign[:10] + "...",
            "fecha_generacion": datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"Error al regenerar TA: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500 