import requests

def construir_soap(token, sign, cuit, datos_cbte_xml):
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:ar="http://ar.gov.afip.dif.FEV1/">
   <soapenv:Header/>
   <soapenv:Body>
      <ar:FECAESolicitar>
         <ar:Auth>
            <ar:Token>{token}</ar:Token>
            <ar:Sign>{sign}</ar:Sign>
            <ar:Cuit>{cuit}</ar:Cuit>
         </ar:Auth>
         {datos_cbte_xml}
      </ar:FECAESolicitar>
   </soapenv:Body>
</soapenv:Envelope>"""

def enviar_comprobante(token, sign, cuit, datos_cbte_xml):
    body = construir_soap(token, sign, cuit, datos_cbte_xml)
    headers = {
        'SOAPAction': 'http://ar.gov.afip.dif.FEV1/FECAESolicitar',
        'Content-Type': 'text/xml; charset=utf-8',
    }
    r = requests.post("https://wswhomo.afip.gov.ar/wsfev1/service.asmx", headers=headers, data=body)
    return r.text

def construir_xml_comprobante(datos):
    """Construye el XML del comprobante según la estructura requerida por AFIP."""
    # Validar campos requeridos
    campos_requeridos = ['tipo_comprobante', 'punto_venta', 'doc_tipo', 'doc_nro', 
                        'cbte_fch', 'imp_neto', 'imp_iva', 'imp_total', 'mon_id', 
                        'concepto', 'condicion_iva_receptor']
    
    for campo in campos_requeridos:
        if campo not in datos:
            raise ValueError(f"Falta el campo requerido: {campo}")

    # Validar tipo de documento
    doc_tipo = int(datos['doc_tipo'])
    doc_nro = str(datos['doc_nro'])
    
    if doc_tipo == 80 and len(doc_nro) != 11:  # CUIT
        raise ValueError("El CUIT debe tener 11 dígitos")
    elif doc_tipo == 96 and len(doc_nro) != 8:  # DNI
        raise ValueError("El DNI debe tener 8 dígitos")
    elif doc_tipo == 99 and doc_nro != "0":  # Consumidor Final
        raise ValueError("Para Consumidor Final, el número de documento debe ser 0")

    # Construir XML
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<FeDetReq>
    <Concepto>{datos['concepto']}</Concepto>
    <DocTipo>{doc_tipo}</DocTipo>
    <DocNro>{doc_nro}</DocNro>
    <CbteDesde>{datos['cbte_desde']}</CbteDesde>
    <CbteHasta>{datos['cbte_hasta']}</CbteHasta>
    <CbteFch>{datos['cbte_fch']}</CbteFch>
    <ImpTotal>{datos['imp_total']}</ImpTotal>
    <ImpNeto>{datos['imp_neto']}</ImpNeto>
    <ImpOpEx>{datos.get('imp_op_ex', '0.00')}</ImpOpEx>
    <ImpTrib>{datos.get('imp_trib', '0.00')}</ImpTrib>
    <ImpIVA>{datos['imp_iva']}</ImpIVA>
    <FchServicio>{datos.get('fch_serv_desde', '')}</FchServicio>
    <FchVtoPago>{datos.get('fch_serv_hasta', '')}</FchVtoPago>
    <MonId>{datos['mon_id']}</MonId>
    <MonCotiz>{datos.get('mon_cotiz', '1.000')}</MonCotiz>
    <CbtesAsoc>
        <CbteAsoc>
            <Tipo>{datos.get('tipo_comprobante')}</Tipo>
            <PtoVta>{datos.get('punto_venta')}</PtoVta>
            <Nro>{datos.get('cbte_desde')}</Nro>
        </CbteAsoc>
    </CbtesAsoc>
    <Tributos>
        {''.join(f'''
        <Tributo>
            <Id>{tributo['Id']}</Id>
            <Desc>{tributo['Desc']}</Desc>
            <BaseImp>{tributo['BaseImp']}</BaseImp>
            <Alic>{tributo['Alic']}</Alic>
            <Importe>{tributo['Importe']}</Importe>
        </Tributo>''' for tributo in datos.get('tributos', []))}
    </Tributos>
    <Iva>
        {''.join(f'''
        <AlicIva>
            <Id>{alicuota['Id']}</Id>
            <BaseImp>{alicuota['BaseImp']}</BaseImp>
            <Importe>{alicuota['Importe']}</Importe>
        </AlicIva>''' for alicuota in datos.get('alicuotas', []))}
    </Iva>
    <Opcionales>
        <Opcional>
            <Id>1</Id>
            <Valor>{datos.get('condicion_iva_receptor')}</Valor>
        </Opcional>
    </Opcionales>
</FeDetReq>"""

    return xml
