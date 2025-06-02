# Fiscalizador ARCA API.

API intermediaria para la fiscalización de comprobantes electrónicos ARCA. Simplifica la integración con los servicios web de ARCA, manejando automáticamente la autenticación, validaciones y comunicación.

## Características Principales

- 🚀 Fiscalización automática de comprobantes electrónicos
- 🔐 Manejo automático de tokens y autenticación ARCA
- ✅ Validaciones según normativa ARCA
- 📝 Numeración automática de comprobantes
- 🔄 Renovación automática de tokens
- 🛡️ Validación de CUITs contra padrón ARCA

## Requisitos

- Python 3.8+
- Certificados ARCA válidos (homologación/producción)
- CUIT habilitado para facturación electrónica
- Punto de venta habilitado

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/fiscalizador-api.git
cd fiscalizador-api

# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales ARCA
```

## Uso Rápido

### Fiscalizar un Comprobante

```python
import requests

# Datos del comprobante
datos = {
    "tipo_comprobante": 1,           # 1=Factura A
    "punto_venta": 12,
    "doc_tipo": 80,                  # 80=CUIT
    "doc_nro": "20396127823",
    "cbte_fch": "20240315",
    "imp_neto": 1000.00,
    "imp_iva": 210.00,
    "imp_total": 1210.00,
    "mon_id": "PES",
    "concepto": 1,
    "condicion_iva_receptor": 1,
    "alicuotas": [
        {
            "Id": 5,                 # 21%
            "BaseImp": 1000.00,
            "Importe": 210.00
        }
    ]
}

# Enviar solicitud
response = requests.post('http://tu-servidor/fiscalizar', json=datos)
resultado = response.json()

if 'error' in resultado:
    print(f"Error: {resultado['error']}")
else:
    print(f"CAE: {resultado['CAE']}")
    print(f"Vencimiento: {resultado['CAEFchVto']}")
```

## Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/fiscalizar` | Fiscaliza un comprobante electrónico |
| GET | `/ultimo-comprobante` | Consulta último comprobante autorizado |
| GET | `/estado-ta` | Verifica estado del Token de Acceso |
| POST | `/regenerar-ta` | Regenera el Token de Acceso |

## Documentación Detallada

Para información detallada sobre:
- Arquitectura del sistema
- Flujos de trabajo
- Validaciones
- Integración con frontend
- Ejemplos de uso
- Guías de implementación

Ver [DOCUMENTACION.md](DOCUMENTACION.md)

## Ambiente

- Homologación: `https://wswhomo.ARCA.gov.ar/...`
- Producción: `https://servicios1.ARCA.gov.ar/...`

## Soporte

Para reportar problemas o solicitar ayuda:
1. Revisar [DOCUMENTACION.md](DOCUMENTACION.md)
2. Abrir un issue en GitHub
3. Contactar al equipo de soporte

## Licencia

MIT
