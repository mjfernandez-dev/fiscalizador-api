import requests  # Importa la librería requests para realizar solicitudes HTTP.

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

def enviar_comprobante(token, sign, cuit, datos_cbte_xml):  # Función para enviar el comprobante a AFIP y recibir la respuesta.
    body = construir_soap(token, sign, cuit, datos_cbte_xml)  # Se construye el cuerpo del mensaje SOAP.
    headers = {  # Se definen los encabezados HTTP necesarios para la solicitud SOAP.
        'SOAPAction': 'http://ar.gov.afip.dif.FEV1/FECAESolicitar',  # Acción SOAP.
        'Content-Type': 'text/xml; charset=utf-8',  # Tipo de contenido.
    }
    # Guardar en archivo (opcional)
    with open("xml_enviado.xml", "w", encoding="utf-8") as f:  # Se guarda el XML enviado para referencia o auditoría.
        f.write(body)
    # Se realiza la solicitud POST a la URL del servicio web de AFIP (entorno de homologación).
    r = requests.post("https://wswhomo.afip.gov.ar/wsfev1/service.asmx", headers=headers, data=body)
    return r.text  # Se devuelve la respuesta como texto plano.

def construir_xml_comprobante(datos):  # Función para construir el XML del comprobante a partir de los datos recibidos.

    # Ajustes especiales para comprobante tipo C (CbteTipo=11)
    if datos['tipo_comprobante'] == 11:
        # Según AFIP, para tipo C estos importes deben ser 0:
        datos['imp_tot_conc'] = '0.00'
        datos['imp_op_ex'] = '0.00'
        datos['imp_iva'] = '0.00'
        datos['alicuotas'] = []  # Para no enviar el bloque <ar:Iva>
    
    # Calcular ImpTotal como ImpNeto + ImpTrib
    imp_neto = float(datos['imp_neto'])
    imp_trib = float(datos.get('imp_trib', 0.00))
    datos['imp_total'] = f"{round(imp_neto + imp_trib, 2):.2f}"  # AFIP exige 2 decimales.

    # Construcción de Tributos
    tributos_xml = ""  # Inicializa la variable que contendrá los tributos.
    if datos.get('tributos'):
        tributos_items = ""
        for t in datos['tributos']:
            tributos_items += f"""
            <ar:Tributo>
                <ar:Id>{t['Id']}</ar:Id>
                <ar:Desc>{t['Desc']}</ar:Desc>
                <ar:BaseImp>{t['BaseImp']}</ar:BaseImp>
                <ar:Alic>{t['Alic']}</ar:Alic>
                <ar:Importe>{t['Importe']}</ar:Importe>
            </ar:Tributo>"""
        tributos_xml = f"<ar:Tributos>{tributos_items}\n</ar:Tributos>"

    # Construcción de Iva
    iva_xml = ""  # Inicializa la variable para el IVA.
    if datos.get('alicuotas') and datos['tipo_comprobante'] != 11:
        iva_items = ""
        for a in datos['alicuotas']:
            iva_items += f"""
            <ar:AlicIva>
                <ar:Id>{a['Id']}</ar:Id>
                <ar:BaseImp>{a['BaseImp']}</ar:BaseImp>
                <ar:Importe>{a['Importe']}</ar:Importe>
            </ar:AlicIva>"""
        iva_xml = f"<ar:Iva>{iva_items}\n</ar:Iva>"

    # Construcción de la cabecera del comprobante
    cabecera = f"""
    <ar:FeCabReq>
        <ar:CantReg>1</ar:CantReg>
        <ar:PtoVta>{datos['punto_venta']}</ar:PtoVta>
        <ar:CbteTipo>{datos['tipo_comprobante']}</ar:CbteTipo>
    </ar:FeCabReq>"""

    # Construcción del detalle del comprobante
    detalle = f"""
    <ar:FeDetReq>
        <ar:FECAEDetRequest>
            <ar:Concepto>{datos['concepto']}</ar:Concepto>
            <ar:DocTipo>{datos['doc_tipo']}</ar:DocTipo>
            <ar:DocNro>{datos['doc_nro']}</ar:DocNro>
            <ar:CbteDesde>{datos['cbte_desde']}</ar:CbteDesde>
            <ar:CbteHasta>{datos['cbte_hasta']}</ar:CbteHasta>
            <ar:CbteFch>{datos['cbte_fch']}</ar:CbteFch>
            <ar:ImpTotal>{datos['imp_total']}</ar:ImpTotal>
            <ar:ImpTotConc>{datos.get('imp_tot_conc', '0.00')}</ar:ImpTotConc>
            <ar:ImpNeto>{datos['imp_neto']}</ar:ImpNeto>
            <ar:ImpOpEx>{datos.get('imp_op_ex', '0.00')}</ar:ImpOpEx>
            <ar:ImpTrib>{datos.get('imp_trib', '0.00')}</ar:ImpTrib>
            <ar:ImpIVA>{datos.get('imp_iva', '0.00')}</ar:ImpIVA>
            <ar:FchServDesde>{datos.get('fch_serv_desde', '')}</ar:FchServDesde>
            <ar:FchServHasta>{datos.get('fch_serv_hasta', '')}</ar:FchServHasta>
            <ar:FchVtoPago>{datos.get('fch_vto_pago', '')}</ar:FchVtoPago>
            <ar:MonId>{datos['mon_id']}</ar:MonId>
            <ar:MonCotiz>{datos.get('mon_cotiz', '1.000')}</ar:MonCotiz>
            <ar:CondicionIVAReceptorId>{datos.get('condicion_iva_receptor', '')}</ar:CondicionIVAReceptorId>
            {tributos_xml}
            {iva_xml}
        </ar:FECAEDetRequest>
    </ar:FeDetReq>"""

    return f"{cabecera}{detalle}"  # Se concatenan y devuelven la cabecera y el detalle del comprobante.
