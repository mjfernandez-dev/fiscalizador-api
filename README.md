# Fiscalizador AFIP API

API intermediaria para la fiscalización de comprobantes electrónicos AFIP.

## Endpoints

### POST /fiscalizar

Endpoint principal para fiscalizar comprobantes electrónicos.

#### Datos Requeridos

```json
{
    "tipo_comprobante": 1,           // 1=Factura A, 6=Factura B, 11=Factura C
    "punto_venta": 12,               // Número de punto de venta
    "doc_tipo": 80,                  // 80=CUIT, 96=DNI, 99=Consumidor Final
    "doc_nro": "20396127823",        // Número de documento (11 dígitos para CUIT, 8 para DNI, 0 para CF)
    "cbte_fch": "20240315",          // Fecha del comprobante (YYYYMMDD)
    "imp_neto": 1000.00,            // Importe neto
    "imp_iva": 210.00,              // Importe IVA
    "imp_total": 1210.00,           // Importe total
    "mon_id": "PES",                // Moneda (PES, USD, EUR)
    "concepto": 1,                  // 1=Productos, 2=Servicios, 3=Productos y Servicios
    "condicion_iva_receptor": 1     // Condición IVA del receptor (ver tabla de condiciones)
}
```

#### Datos Opcionales

```json
{
    "imp_op_ex": 0.00,              // Importe operaciones exentas
    "imp_trib": 0.00,               // Importe tributos
    "fch_serv_desde": "20240315",   // Fecha de inicio del servicio (YYYYMMDD)
    "fch_serv_hasta": "20240315",   // Fecha de fin del servicio (YYYYMMDD)
    "mon_cotiz": 1.000,            // Cotización de la moneda
    "alicuotas": [                  // Array de alícuotas de IVA
        {
            "Id": 5,               // 5=21%, 4=10.5%, 3=27%, 2=5%, 1=2.5%, 6=0%
            "BaseImp": 1000.00,
            "Importe": 210.00
        }
    ],
    "tributos": [                   // Array de tributos
        {
            "Id": 99,              // ID del tributo
            "Desc": "Impuesto Municipal",
            "BaseImp": 1000.00,
            "Alic": 3.00,
            "Importe": 30.00
        }
    ]
}
```

#### Respuesta Exitosa

```json
{
    "CAE": "12345678901234",        // CAE asignado
    "CAEFchVto": "20240415",        // Fecha de vencimiento del CAE
    "CbteNro": 1,                   // Número de comprobante asignado
    "PtoVta": 12,                   // Punto de venta
    "CbteTipo": 1                   // Tipo de comprobante
}
```

#### Respuesta de Error

```json
{
    "error": "Mensaje de error detallado"
}
```

### GET /ultimo-comprobante

Consulta el último comprobante autorizado para un punto de venta y tipo de comprobante.

#### Parámetros Query

- `pto_vta`: Punto de venta (default: 12)
- `cbte_tipo`: Tipo de comprobante (default: 1)

#### Respuesta Exitosa

```json
{
    "ultimo_comprobante": {
        "punto_venta": 12,
        "tipo_comprobante": 1,
        "ultimo_numero": 123,
        "fecha_ultimo": "2024-03-15T10:30:00"
    },
    "siguiente_numero": 124,
    "punto_venta": 12,
    "tipo_comprobante": 1
}
```

### GET /estado-ta

Consulta el estado del Token de Acceso (TA).

#### Respuesta Exitosa

```json
{
    "existe": true,
    "fecha_creacion": "2024-03-15T10:00:00",
    "fecha_expiracion": "2024-03-15T10:10:00",
    "token": "abc123...",
    "sign": "def456...",
    "expirado": false
}
```

### POST /regenerar-ta

Regenera el Token de Acceso (TA).

#### Respuesta Exitosa

```json
{
    "mensaje": "TA regenerado exitosamente",
    "token": "abc123...",
    "sign": "def456...",
    "fecha_generacion": "2024-03-15T10:00:00"
}
```

## Condiciones IVA Receptor

1. IVA Responsable Inscripto
2. IVA Responsable no Inscripto
3. IVA no Responsable
4. IVA Sujeto Exento
5. Consumidor Final
6. Responsable Monotributo
7. Sujeto no Categorizado
8. Proveedor del Exterior
9. Cliente del Exterior
10. IVA Liberado
11. IVA Responsable Inscripto - Agente de Percepción
12. Pequeño Contribuyente Eventual
13. Monotributista Social
14. Pequeño Contribuyente Eventual Social

## Notas Importantes

1. El sistema maneja automáticamente:
   - Obtención y renovación del Token de Acceso (TA)
   - Numeración automática de comprobantes
   - Validación de datos según reglas AFIP
   - Construcción del XML requerido
   - Comunicación con los servicios de AFIP

2. Para usar la API, el cliente solo necesita:
   - Enviar los datos del comprobante en el formato especificado
   - Manejar las respuestas exitosas y errores
   - No necesita preocuparse por certificados, tokens o detalles técnicos

3. El sistema está configurado para ambiente de homologación (testing). Para producción, se requiere:
   - Certificados válidos de producción
   - CUIT habilitado para facturación electrónica
   - Punto de venta habilitado
   - Modificación de URLs a ambiente de producción
