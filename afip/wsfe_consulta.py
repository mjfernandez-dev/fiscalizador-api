from zeep import Client
from zeep.wsse.username import UsernameToken
import xml.etree.ElementTree as ET

def consultar_ultimo_autorizado(token, sign, cuit, pto_vta, cbte_tipo):
    """
    Consulta el último comprobante autorizado para un punto de venta y tipo de comprobante.
    Args:
        token: Token de autenticación
        sign: Firma digital
        cuit: CUIT del emisor
        pto_vta: Punto de venta
        cbte_tipo: Tipo de comprobante
    Returns:
        dict: Información del último comprobante autorizado
    Raises:
        Exception: Si hay errores en la comunicación o en la respuesta de AFIP
    """
    client = Client(
        'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
        wsse=UsernameToken(token, sign)
    )

    params = {
        'Auth': {
            'Token': token,
            'Sign': sign,
            'Cuit': cuit
        },
        'PtoVta': pto_vta,
        'CbteTipo': cbte_tipo
    }

    try:
        response = client.service.FECompUltimoAutorizado(**params)
        resultado = {
            'punto_venta': getattr(response, 'PtoVta', None),
            'tipo_comprobante': getattr(response, 'CbteTipo', None),
            'ultimo_numero': getattr(response, 'CbteNro', None),
            'fecha_ultimo': getattr(response, 'FchProceso', None)
        }
        return resultado

    except Exception as e:
        try:
            if hasattr(e, 'detail'):
                error_xml = ET.fromstring(str(e.detail))
                codigo = error_xml.find('.//Code')
                mensaje = error_xml.find('.//Msg')
                if codigo is not None and mensaje is not None:
                    raise Exception(f"Error AFIP {codigo.text}: {mensaje.text}")
        except:
            pass
        raise Exception(f"Error al consultar último comprobante: {str(e)}")
