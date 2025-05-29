from zeep import Client
from zeep.transports import Transport
from zeep.wsse.signature import Signature
from zeep.wsse.username import UsernameToken
import xml.etree.ElementTree as ET

def consultar_ultimo_autorizado(token, sign, cuit, pto_vta, cbte_tipo):
    """
    Consulta el último comprobante autorizado para un punto de venta y tipo de comprobante.
    
    Args:
        token (str): Token de autenticación
        sign (str): Firma digital
        cuit (str): CUIT del emisor
        pto_vta (int): Punto de venta
        cbte_tipo (int): Tipo de comprobante (1=Factura A, 6=Factura B, etc.)
    
    Returns:
        dict: Información del último comprobante autorizado
    """
    # Crear cliente SOAP
    client = Client(
        'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
        wsse=UsernameToken(token, sign)
    )

    # Preparar parámetros
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
        # Llamar al servicio
        response = client.service.FECompUltimoAutorizado(**params)
        
        # Convertir la respuesta a un diccionario más amigable
        # La respuesta real de AFIP tiene esta estructura
        resultado = {
            'punto_venta': response.PtoVta,
            'tipo_comprobante': response.CbteTipo,
            'ultimo_numero': response.CbteNro,
            'fecha_ultimo': response.FchProceso if hasattr(response, 'FchProceso') else None
        }
        
        # Agregar información adicional si está disponible
        if hasattr(response, 'PtoVta'):
            resultado['punto_venta'] = response.PtoVta
        if hasattr(response, 'CbteTipo'):
            resultado['tipo_comprobante'] = response.CbteTipo
        if hasattr(response, 'CbteNro'):
            resultado['ultimo_numero'] = response.CbteNro
            
        return resultado
        
    except Exception as e:
        # Si hay un error en la respuesta SOAP, intentar extraer el mensaje de error
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