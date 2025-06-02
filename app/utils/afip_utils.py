"""
Utilidades para el manejo de AFIP.
Contiene funciones auxiliares para el manejo de tokens y comprobantes.
"""
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from afip.wsaa import obtener_ta, extraer_token_sign, verificar_token_valido
from afip.wsfe_consulta import consultar_ultimo_autorizado
from afip.wsfe import validar_cuit_receptor

from app.config import CERT, KEY, CUIT, TOKEN_FILE

def obtener_fecha_actual_utc():
    """Obtiene la fecha actual en UTC para comparar con el token de AFIP."""
    return datetime.now(timezone.utc)

def obtener_token_afip(servicio='wsfe'):
    """Obtiene un token válido para el servicio especificado."""
    try:
        # Verificar si existe y es válido
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as f:
                ta_xml = f.read()
                if verificar_token_valido(ta_xml):
                    return extraer_token_sign(ta_xml)
                else:
                    os.remove(TOKEN_FILE)
        
        # Generar nuevo token
        ta_xml = obtener_ta(CERT, KEY, servicio=servicio)
        with open(TOKEN_FILE, "w") as f:
            f.write(ta_xml)
        
        return extraer_token_sign(ta_xml)
    
    except Exception as e:
        raise ValueError(f"Error al obtener token AFIP: {str(e)}")

def validar_cuit_y_obtener_token(cuit):
    """Valida un CUIT y obtiene un token para el padrón A5."""
    ta_xml = obtener_ta(CERT, KEY, servicio='ws_sr_padron_a5')
    token, sign = extraer_token_sign(ta_xml)
    validar_cuit_receptor(token, sign, cuit)
    return token, sign

def consultar_ultimo_comprobante(pto_vta, cbte_tipo):
    """Consulta el último comprobante autorizado para un punto de venta y tipo."""
    token, sign = obtener_token_afip()
    return consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo) 