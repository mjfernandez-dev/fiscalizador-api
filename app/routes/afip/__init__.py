"""
Blueprint para las rutas relacionadas con ARCA.
Crea y registra el blueprint con sus rutas.
"""
from flask import Blueprint
from .fiscalizacion import fiscalizar, ultimo_comprobante, estado_ta, regenerar_ta

# Crear blueprint
bp = Blueprint('ARCA', __name__, url_prefix='/ARCA')

# Registrar rutas
bp.add_url_rule('/fiscalizar', 'fiscalizar', fiscalizar, methods=['POST'])
bp.add_url_rule('/ultimo-comprobante', 'ultimo_comprobante', ultimo_comprobante, methods=['GET'])
bp.add_url_rule('/estado-ta', 'estado_ta', estado_ta, methods=['GET'])
bp.add_url_rule('/regenerar-ta', 'regenerar_ta', regenerar_ta, methods=['POST'])  