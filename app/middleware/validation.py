"""
Middleware de validación.
Contiene funciones para sanitizar y validar datos de entrada.
"""
from flask import request

def sanitize_input(data):
    """Función para sanitizar datos de entrada."""
    if isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, str):
        # Eliminar caracteres potencialmente peligrosos
        return ''.join(c for c in data if c.isprintable())
    return data

def validate_input_data(data):
    """Función para validar datos de entrada requeridos."""
    required_fields = ['tipo_comprobante', 'doc_tipo', 'doc_nro', 'imp_neto']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Campo requerido faltante: {field}")
    
    # Validar tipos de datos
    if not isinstance(data.get('tipo_comprobante'), (int, str)) or \
       not isinstance(data.get('doc_tipo'), (int, str)) or \
       not isinstance(data.get('doc_nro'), (int, str)):
        raise ValueError("Los campos tipo_comprobante, doc_tipo y doc_nro deben ser números")
    
    # Validar importes
    try:
        float(data.get('imp_neto', '0'))
    except ValueError:
        raise ValueError("El importe neto debe ser un número válido") 