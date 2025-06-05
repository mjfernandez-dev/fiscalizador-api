import requests
import time
from lxml import etree

def construir_soap(token, sign, cuit, datos_cbte_xml):
    # Determinar si debemos incluir IVA y Tributos
    tipo_comprobante = int(datos_cbte_xml['tipo_comprobante'])
    imp_trib = float(datos_cbte_xml.get('imp_trib', '0.00'))
    
    # No incluir IVA para comprobantes tipo C (11)
    incluir_iva = tipo_comprobante != 11
    # No incluir tributos si el importe es 0
    incluir_tributos = imp_trib > 0
    
    # Construir el XML base
    xml_base = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:ar="http://ar.gov.afip.dif.FEV1/">
   <soapenv:Header/>
   <soapenv:Body>
      <ar:FECAESolicitar>
         <ar:Auth>
            <ar:Token>{token}</ar:Token>
            <ar:Sign>{sign}</ar:Sign>
            <ar:Cuit>{cuit}</ar:Cuit>
         </ar:Auth>
         <ar:FeCAEReq>
            <ar:FeCabReq>
               <ar:CantReg>1</ar:CantReg>
               <ar:PtoVta>{datos_cbte_xml['punto_venta']}</ar:PtoVta>
               <ar:CbteTipo>{datos_cbte_xml['tipo_comprobante']}</ar:CbteTipo>
            </ar:FeCabReq>
            <ar:FeDetReq>
               <ar:FECAEDetRequest>
                  <ar:Concepto>{datos_cbte_xml['concepto']}</ar:Concepto>
                  <ar:DocTipo>{datos_cbte_xml['doc_tipo']}</ar:DocTipo>
                  <ar:DocNro>{datos_cbte_xml['doc_nro']}</ar:DocNro>
                  <ar:CbteDesde>{datos_cbte_xml['cbte_desde']}</ar:CbteDesde>
                  <ar:CbteHasta>{datos_cbte_xml['cbte_hasta']}</ar:CbteHasta>
                  <ar:CbteFch>{datos_cbte_xml['cbte_fch']}</ar:CbteFch>
                  <ar:ImpTotal>{datos_cbte_xml['imp_total']}</ar:ImpTotal>
                  <ar:ImpNeto>{datos_cbte_xml['imp_neto']}</ar:ImpNeto>
                  <ar:ImpOpEx>{datos_cbte_xml.get('imp_op_ex', '0.00')}</ar:ImpOpEx>
                  <ar:ImpTrib>{datos_cbte_xml.get('imp_trib', '0.00')}</ar:ImpTrib>
                  <ar:ImpIVA>{datos_cbte_xml.get('imp_iva', '0.00')}</ar:ImpIVA>
                  <ar:FchServDesde>{datos_cbte_xml.get('fch_serv_desde', '')}</ar:FchServDesde>
                  <ar:FchServHasta>{datos_cbte_xml.get('fch_serv_hasta', '')}</ar:FchServHasta>
                  <ar:FchVtoPago>{datos_cbte_xml.get('fch_vto_pago', '')}</ar:FchVtoPago>
                  <ar:MonId>{datos_cbte_xml['mon_id']}</ar:MonId>
                  <ar:MonCotiz>{datos_cbte_xml.get('mon_cotiz', '1.000')}</ar:MonCotiz>"""
    
    # Agregar IVA solo si es necesario
    if incluir_iva and datos_cbte_xml.get('alicuotas'):
        xml_base += f"""
                  <ar:Iva>
                    {"".join([
                      f"<ar:AlicIva>"
                      f"<ar:Id>{iva['Id']}</ar:Id>"
                      f"<ar:BaseImp>{iva['BaseImp']}</ar:BaseImp>"
                      f"<ar:Importe>{iva['Importe']}</ar:Importe>"
                      f"</ar:AlicIva>"
                      for iva in datos_cbte_xml['alicuotas']
                    ])}
                  </ar:Iva>"""
    
    # Agregar Tributos solo si es necesario
    if incluir_tributos and datos_cbte_xml.get('tributos'):
        xml_base += f"""
                  <ar:Tributos>
                    {"".join([
                      f"<ar:Tributo>"
                      f"<ar:Id>{trib['Id']}</ar:Id>"
                      f"<ar:Desc>{trib['Desc']}</ar:Desc>"
                      f"<ar:BaseImp>{trib['BaseImp']}</ar:BaseImp>"
                      f"<ar:Alic>{trib['Alic']}</ar:Alic>"
                      f"<ar:Importe>{trib['Importe']}</ar:Importe>"
                      f"</ar:Tributo>"
                      for trib in datos_cbte_xml['tributos']
                    ])}
                  </ar:Tributos>"""
    
    # Cerrar el XML
    xml_base += """
               </ar:FECAEDetRequest>
            </ar:FeDetReq>
         </ar:FeCAEReq>
      </ar:FECAESolicitar>
   </soapenv:Body>
</soapenv:Envelope>"""
    
    return xml_base

def enviar_comprobante(token, sign, cuit, datos_cbte_dict):
    body = construir_soap(token, sign, cuit, datos_cbte_dict)
    headers = {
        'SOAPAction': 'http://ar.gov.afip.dif.FEV1/FECAESolicitar',
        'Content-Type': 'text/xml; charset=utf-8',
    }
    
    # Configuración de timeout
    timeout = (30, 30)  # (connect timeout, read timeout)
    
    try:
        print("Enviando request a AFIP...")
        print("Body:", body)  # Log del XML enviado
        
        r = requests.post(
            "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
            headers=headers,
            data=body,
            timeout=timeout,
            verify=True  # Verificar certificado SSL
        )
        
        print("Status code:", r.status_code)  # Log del código de estado
        print("Response headers:", r.headers)  # Log de los headers
        
        # Solo lanzar excepción si no es 200 OK
        if r.status_code != 200:
            r.raise_for_status()
        
        print("Response body:", r.text)  # Log del cuerpo de la respuesta
            
        # Verificar si hay errores en el cuerpo de la respuesta
        xml_resp = etree.fromstring(r.text.encode())
        
        # Definir el namespace
        ns = {'ns': 'http://ar.gov.afip.dif.FEV1/'}
        
        # Verificar si hay errores en la respuesta
        errores = xml_resp.findall(".//ns:Err", namespaces=ns)
        if errores:
            mensajes_error = [f"{err.findtext('ns:Code', namespaces=ns)}: {err.findtext('ns:Msg', namespaces=ns)}" for err in errores]
            raise Exception("Error de AFIP: " + " | ".join(mensajes_error))
        
        # Verificar el resultado usando la ruta correcta con namespace
        resultado = xml_resp.findtext(".//ns:FeCabResp/ns:Resultado", namespaces=ns)
        print(f"Resultado encontrado: {resultado}")  # Debug log
        
        if resultado == "A":  # A = Aprobado
            # Extraer la información exitosa usando las rutas correctas con namespace
            cae = xml_resp.findtext(".//ns:FECAEDetResponse/ns:CAE", namespaces=ns)
            cae_fch_vto = xml_resp.findtext(".//ns:FECAEDetResponse/ns:CAEFchVto", namespaces=ns)
            
            if not all([cae, cae_fch_vto]):
                raise Exception("Error de AFIP: La respuesta no contiene CAE o fecha de vencimiento")
            
            # Verificar si hay observaciones (advertencias)
            observaciones = xml_resp.findall(".//ns:FECAEDetResponse/ns:Observaciones/ns:Obs", namespaces=ns)
            if observaciones:
                mensajes_obs = [f"{obs.findtext('ns:Code', namespaces=ns)}: {obs.findtext('ns:Msg', namespaces=ns)}" for obs in observaciones]
                print("Observaciones de AFIP:", mensajes_obs)  # Log de observaciones
            
            return r.text
        elif resultado == "R":  # R = Rechazado
            # Buscar observaciones de AFIP
            observaciones = xml_resp.findall(".//ns:FECAEDetResponse/ns:Observaciones/ns:Obs", namespaces=ns)
            if observaciones:
                mensajes_error = [f"{obs.findtext('ns:Code', namespaces=ns)}: {obs.findtext('ns:Msg', namespaces=ns)}" for obs in observaciones]
                raise Exception("Error de AFIP: " + " | ".join(mensajes_error))
            else:
                raise Exception("Error de AFIP: El comprobante fue rechazado sin mensaje de error específico")
        else:
            print(f"XML completo recibido: {r.text}")  # Debug log
            raise Exception(f"Error de AFIP: Resultado inesperado '{resultado}'")
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error al conectar con AFIP: {str(e)}")
    except Exception as e:
        raise e
