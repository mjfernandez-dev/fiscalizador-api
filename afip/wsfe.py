import requests  # Importa la librería requests para realizar solicitudes HTTP.
from zeep import Client
from zeep.transports import Transport
from zeep.wsse.signature import Signature
from zeep.wsse.username import UsernameToken
import xml.etree.ElementTree as ET
from .config import CUIT, CERT, KEY  # Importamos CUIT, CERT y KEY desde config.py
from afip.wsaa import obtener_ta, SERVICIOS, extraer_token_sign  # Agregamos extraer_token_sign a la importación

def validar_cuit_receptor(token, sign, cuit):
    """Valida que el CUIT del receptor exista y esté activo usando el servicio de Padrón A5"""
    try:
        # Obtener token específico para Padrón A5
        ta_xml = obtener_ta(CERT, KEY, servicio='ws_sr_padron_a5')
        token_padron, sign_padron = extraer_token_sign(ta_xml)

        # Crear cliente para el servicio de Padrón A5
        client = Client(SERVICIOS['ws_sr_padron_a5'])
        
        # Consultar persona
        response = client.service.getPersona(
            token=token_padron,
            sign=sign_padron,
            cuitRepresentada=CUIT,
            idPersona=cuit
        )

        if not response or not hasattr(response, 'personaReturn'):
            raise ValueError(f"No se pudo obtener información del CUIT {cuit}")

        persona = response.personaReturn
        if not persona or not hasattr(persona, 'idPersona'):
            raise ValueError(f"El CUIT {cuit} no existe en el padrón de AFIP")

        # Verificar estado
        if hasattr(persona, 'estado') and persona.estado != 'ACTIVO':
            raise ValueError(f"El CUIT {cuit} no está activo en el padrón de AFIP")

        return True

    except Exception as e:
        raise ValueError(f"Error al validar CUIT {cuit}: {str(e)}")

def construir_soap(token, sign, cuit, datos_cbte_xml):  # Función para construir el mensaje SOAP que se enviará a AFIP.
    # Se retorna una cadena XML con el formato SOAP estándar.
    # Se insertan dinámicamente el token, sign y CUIT en la cabecera de autenticación.
    # En el cuerpo se inserta el XML del comprobante previamente generado.
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:ar="http://ar.gov.afip.dif.FEV1/">
   <soapenv:Header/>
   <soapenv:Body>
      <ar:FECAESolicitar>
         <ar:Auth>
            <ar:Token>{token}</ar:Token>  <!-- Token devuelto por AFIP para autenticación. -->
            <ar:Sign>{sign}</ar:Sign>  <!-- Firma digital devuelta por AFIP. -->
            <ar:Cuit>{cuit}</ar:Cuit>  <!-- CUIT de la empresa emisora. -->
         </ar:Auth>
         <ar:FeCAEReq>
            {datos_cbte_xml}  <!-- XML del comprobante a autorizar. -->
         </ar:FeCAEReq>
      </ar:FECAESolicitar>
   </soapenv:Body>
</soapenv:Envelope>"""

def enviar_comprobante(token, sign, cuit, datos_cbte_xml):
    """Envía el comprobante a AFIP usando el servicio SOAP."""
    try:
        # Crear cliente SOAP
        client = Client(
            'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
            wsse=UsernameToken(token, sign)
        )

        # Definir namespaces
        namespaces = {
            'ar': 'http://ar.gov.afip.dif.FEV1/',
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/'
        }

        # Registrar los namespaces
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)

        # Parsear el XML con los namespaces registrados
        root = ET.fromstring(datos_cbte_xml)
        
        # Preparar parámetros
        params = {
            'Auth': {
                'Token': token,
                'Sign': sign,
                'Cuit': cuit
            },
            'FeCAEReq': root
        }

        # Llamar al servicio
        response = client.service.FECAESolicitar(**params)
        
        # Convertir la respuesta a XML
        xml_response = ET.tostring(response, encoding='unicode', pretty_print=True)
        
        # Guardar en archivo para debugging
        with open("xml_respuesta.xml", "w", encoding="utf-8") as f:
            f.write(xml_response)
            
        return xml_response

    except Exception as e:
        # Si hay un error en la respuesta SOAP, intentar extraer el mensaje de error
        try:
            if hasattr(e, 'detail'):
                error_xml = ET.fromstring(str(e.detail))
                codigo = error_xml.find('.//Code')
                mensaje = error_xml.find('.//Msg')
                if codigo is not None and mensaje is not None:
                    raise ValueError(f"Error AFIP {codigo.text}: {mensaje.text}")
        except:
            pass
        raise ValueError(f"Error al enviar comprobante: {str(e)}")

def construir_xml_comprobante(datos):
    print("Construyendo XML con datos:", datos)  # Log de datos de entrada

    # Definir namespaces
    namespaces = {
        'ar': 'http://ar.gov.afip.dif.FEV1/',
        'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/'
    }

    # Registrar los namespaces
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    # Validar CUIT del receptor si es tipo 80 (CUIT)
    if datos.get('doc_tipo') == 80 and datos.get('doc_nro'):
        try:
            validar_cuit_receptor(token, sign, datos['doc_nro'])
        except ValueError as e:
            raise ValueError(f"Error en CUIT del receptor: {str(e)}")

    # Validaciones iniciales
    imp_neto = float(datos.get('imp_neto', '0.00'))
    if imp_neto > 0:
        if not datos.get('alicuotas'):
            raise ValueError("Si el importe neto es mayor a 0, se deben especificar las alícuotas de IVA")
        if not datos.get('condicion_iva_receptor'):
            raise ValueError("Si el importe neto es mayor a 0, se debe especificar la condición IVA del receptor")
        
        # Validar que la suma de las bases imponibles coincida con el importe neto
        suma_bases = sum(float(a.get('BaseImp', 0)) for a in datos.get('alicuotas', []))
        if abs(suma_bases - imp_neto) > 0.01:  # Permitimos una pequeña diferencia por redondeo
            raise ValueError(
                f"La suma de las bases imponibles ({suma_bases:.2f}) no coincide con el importe neto ({imp_neto:.2f}). "
                f"Las bases imponibles deben sumar exactamente el importe neto."
            )

    # Asegurar que los valores numéricos tengan el formato correcto
    def formatear_numero(valor, decimales=2):
        try:
            if valor is None or valor == '':
                return '0.00'
            num = float(valor)
            return f"{num:.{decimales}f}"
        except (ValueError, TypeError):
            print(f"Error al formatear número: {valor}")
            return '0.00'

    # Validar alícuotas de IVA
    def validar_alicuota(base_imp, alic_id, importe, imp_neto_total):
        """Valida que el importe de IVA corresponda con la alícuota y la base imponible"""
        alic_porcentajes = {
            '3': 0.0,    # 0%
            '4': 0.105,  # 10.5%
            '5': 0.21,   # 21%
            '6': 0.27,   # 27%
            '8': 0.05,   # 5%
            '9': 0.025   # 2.5%
        }
        
        if alic_id not in alic_porcentajes:
            raise ValueError(f"Alícuota {alic_id} no válida. Valores permitidos: {list(alic_porcentajes.keys())}")
        
        base = float(base_imp)
        if base > imp_neto_total:
            raise ValueError(
                f"La base imponible ({base:.2f}) no puede ser mayor que el importe neto total ({imp_neto_total:.2f})"
            )
        
        importe_calculado = base * alic_porcentajes[alic_id]
        importe_ingresado = float(importe)
        
        # Permitimos una pequeña diferencia por redondeo (0.01)
        if abs(importe_calculado - importe_ingresado) > 0.01:
            raise ValueError(
                f"El importe de IVA no coincide con la alícuota. "
                f"Base: {base_imp}, Alícuota: {alic_id} ({alic_porcentajes[alic_id]*100}%), "
                f"Importe calculado: {formatear_numero(importe_calculado)}, "
                f"Importe ingresado: {importe}"
            )

    # Ajustes especiales para comprobante tipo C (CbteTipo=11)
    if datos['tipo_comprobante'] == 11:
        print("Ajustando valores para comprobante tipo C")
        datos['imp_tot_conc'] = '0.00'
        datos['imp_op_ex'] = '0.00'
        datos['imp_iva'] = '0.00'
        datos['alicuotas'] = []
        datos['condicion_iva_receptor'] = '5'  # Consumidor Final para tipo C

    # Formatear todos los valores numéricos
    campos_numericos = ['imp_neto', 'imp_tot_conc', 'imp_op_ex', 'imp_trib', 'imp_iva', 'imp_total']
    for campo in campos_numericos:
        if campo in datos:
            datos[campo] = formatear_numero(datos[campo])
            print(f"Campo {campo} formateado: {datos[campo]}")

    # Calcular ImpTotal como ImpNeto + ImpTrib + ImpIVA
    imp_neto = float(datos['imp_neto'])
    imp_trib = float(datos.get('imp_trib', '0.00'))
    imp_iva = float(datos.get('imp_iva', '0.00'))
    datos['imp_total'] = formatear_numero(imp_neto + imp_trib + imp_iva)
    print(f"Total calculado: {datos['imp_total']}")

    # Construcción de Tributos
    tributos_xml = ""
    if datos.get('tributos'):
        print("Procesando tributos:", datos['tributos'])
        tributos_items = ""
        for t in datos['tributos']:
            # Formatear valores numéricos de tributos
            base_imp = formatear_numero(t.get('BaseImp', '0.00'))
            alic = formatear_numero(t.get('Alic', '0.00'))
            importe = formatear_numero(t.get('Importe', '0.00'))
            
            tributos_items += f"""
            <ar:Tributo>
                <ar:Id>{t['Id']}</ar:Id>
                <ar:Desc>{t['Desc']}</ar:Desc>
                <ar:BaseImp>{base_imp}</ar:BaseImp>
                <ar:Alic>{alic}</ar:Alic>
                <ar:Importe>{importe}</ar:Importe>
            </ar:Tributo>"""
        tributos_xml = f"<ar:Tributos>{tributos_items}\n</ar:Tributos>"
        print("XML de tributos generado:", tributos_xml)

    # Construcción de Iva
    iva_xml = ""
    if datos.get('alicuotas') and datos['tipo_comprobante'] != 11:
        print("Procesando alícuotas:", datos['alicuotas'])
        iva_items = ""
        imp_iva_total = 0.0
        
        for a in datos['alicuotas']:
            # Formatear valores numéricos de alícuotas
            base_imp = formatear_numero(a.get('BaseImp', '0.00'))
            importe = formatear_numero(a.get('Importe', '0.00'))
            alic_id = str(a['Id'])
            
            # Validar que el importe corresponda con la alícuota y la base
            validar_alicuota(base_imp, alic_id, importe, imp_neto)
            
            imp_iva_total += float(importe)
            
            iva_items += f"""
            <ar:AlicIva>
                <ar:Id>{alic_id}</ar:Id>
                <ar:BaseImp>{base_imp}</ar:BaseImp>
                <ar:Importe>{importe}</ar:Importe>
            </ar:AlicIva>"""
        
        # Actualizar el imp_iva total
        datos['imp_iva'] = formatear_numero(imp_iva_total)
        iva_xml = f"<ar:Iva>{iva_items}\n</ar:Iva>"
        print("XML de IVA generado:", iva_xml)

    # Construcción de la cabecera del comprobante
    cabecera = f"""<?xml version="1.0" encoding="UTF-8"?>
<ar:FeCabReq xmlns:ar="{namespaces['ar']}">
    <ar:CantReg>1</ar:CantReg>
    <ar:PtoVta>{int(datos['punto_venta'])}</ar:PtoVta>
    <ar:CbteTipo>{int(datos['tipo_comprobante'])}</ar:CbteTipo>
</ar:FeCabReq>"""
    print("Cabecera generada:", cabecera)

    # Construcción del detalle del comprobante
    detalle = f"""<ar:FeDetReq xmlns:ar="{namespaces['ar']}">
    <ar:FECAEDetRequest>
        <ar:Concepto>{int(datos['concepto'])}</ar:Concepto>
        <ar:DocTipo>{int(datos['doc_tipo'])}</ar:DocTipo>
        <ar:DocNro>{int(datos['doc_nro'])}</ar:DocNro>
        <ar:CbteDesde>{int(datos['cbte_desde'])}</ar:CbteDesde>
        <ar:CbteHasta>{int(datos['cbte_hasta'])}</ar:CbteHasta>
        <ar:CbteFch>{datos['cbte_fch']}</ar:CbteFch>
        <ar:ImpTotal>{datos['imp_total']}</ar:ImpTotal>
        <ar:ImpTotConc>{datos.get('imp_tot_conc', '0.00')}</ar:ImpTotConc>
        <ar:ImpNeto>{datos['imp_neto']}</ar:ImpNeto>
        <ar:ImpOpEx>{datos.get('imp_op_ex', '0.00')}</ar:ImpOpEx>
        <ar:ImpTrib>{datos.get('imp_trib', '0.00')}</ar:ImpTrib>
        <ar:ImpIVA>{datos['imp_iva']}</ar:ImpIVA>
        <ar:FchServDesde>{datos.get('fch_serv_desde', '')}</ar:FchServDesde>
        <ar:FchServHasta>{datos.get('fch_serv_hasta', '')}</ar:FchServHasta>
        <ar:FchVtoPago>{datos.get('fch_vto_pago', '')}</ar:FchVtoPago>
        <ar:MonId>{datos['mon_id']}</ar:MonId>
        <ar:MonCotiz>{datos.get('mon_cotiz', '1.000')}</ar:MonCotiz>
        <ar:CondicionIVAReceptorId>{int(datos.get('condicion_iva_receptor', '5'))}</ar:CondicionIVAReceptorId>
        {tributos_xml}
        {iva_xml}
    </ar:FECAEDetRequest>
</ar:FeDetReq>"""
    print("Detalle generado:", detalle)

    xml_final = f"{cabecera}{detalle}"
    print("XML final generado:", xml_final)
    return xml_final
