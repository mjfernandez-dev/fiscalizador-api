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
import requests

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
            
            # Verificar resultado de FeCabResp
            if not respuesta_afip.get('resultado'):
                return jsonify({"error": "No se recibió resultado de AFIP"}), 400

            if respuesta_afip['resultado'] != 'A':
                mensaje = "Error de AFIP: "
                if respuesta_afip.get('errors'):
                    mensaje += " | ".join([f"{err['code']}: {err['msg']}" for err in respuesta_afip['errors']])
                else:
                    mensaje += "Respuesta rechazada sin detalles"
                return jsonify({"error": mensaje}), 400

            # Verificar respuesta del comprobante
            if not respuesta_afip.get('fe_det_resp'):
                return jsonify({"error": "No se recibió respuesta del comprobante"}), 400

            detalle = respuesta_afip['fe_det_resp'][0]
            if not detalle.get('resultado'):
                return jsonify({"error": "No se recibió resultado del comprobante"}), 400

            if detalle['resultado'] != 'A':
                mensaje = "Error en comprobante: "
                if detalle.get('observaciones'):
                    mensaje += " | ".join([f"{obs['code']}: {obs['msg']}" for obs in detalle['observaciones']])
                else:
                    mensaje += "Comprobante rechazado sin detalles"
                return jsonify({"error": mensaje}), 400

            # Si todo está bien, devolver la respuesta completa
            return jsonify({
                "resultado": "success",
                "comprobante": {
                    "cae": detalle.get('cae'),
                    "cae_fch_vto": detalle.get('cae_fch_vto'),
                    "cbte_desde": detalle.get('cbte_desde'),
                    "cbte_hasta": detalle.get('cbte_hasta'),
                    "cbte_fch": detalle.get('cbte_fch'),
                    "resultado": detalle.get('resultado'),
                    "observaciones": detalle.get('observaciones', [])
                },
                "xml_original": datos_cbte_xml
            })

        except ValueError as e:
            logging.error(f"Error de validación: {str(e)}")
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

        try:
            resultado = consultar_ultimo_comprobante(pto_vta, cbte_tipo)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Error de conexión al consultar último comprobante: {str(e)}")
            return jsonify({
                "error": "Error de conexión con AFIP. Por favor, intente nuevamente en unos segundos.",
                "detalles": "El servicio de AFIP no está respondiendo correctamente."
            }), 503
        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout al consultar último comprobante: {str(e)}")
            return jsonify({
                "error": "Timeout al consultar con AFIP. Por favor, intente nuevamente.",
                "detalles": "El servicio de AFIP está tardando demasiado en responder."
            }), 504
        except Exception as e:
            logging.error(f"Error al consultar último comprobante: {str(e)}", exc_info=True)
            return jsonify({
                "error": "Error al consultar con AFIP",
                "detalles": str(e)
            }), 500

        # Si llegamos aquí, la consulta fue exitosa
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
        logging.error(f"Error inesperado en último comprobante: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "detalles": "Ocurrió un error inesperado al procesar la solicitud."
        }), 500

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