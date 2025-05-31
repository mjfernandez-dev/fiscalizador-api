from flask import Flask, request, jsonify, send_from_directory  # Importa el microframework Flask y funciones auxiliares para manejar solicitudes y servir archivos.
from afip.wsaa import obtener_ta, extraer_token_sign, generar_tra, firmar_tra  # Importa funciones para autenticación con AFIP (WSAA).
from afip.wsfe import enviar_comprobante, construir_xml_comprobante  # Importa funciones para construir y enviar comprobantes electrónicos.
from afip.wsfe_consulta import consultar_ultimo_autorizado  # Importa la función para consultar el último comprobante autorizado por AFIP.
from afip.config import CERT, KEY, CUIT  # Importa constantes de configuración como el certificado, clave y CUIT de la empresa.
from datetime import datetime  # Importa la clase datetime para trabajar con fechas y horas.
import os  # Importa el módulo os para interactuar con el sistema de archivos.
import xml.etree.ElementTree as ET  # Importa el módulo para parsear y manipular XML.

app = Flask(__name__)  # Se crea una instancia de la aplicación Flask.

@app.route("/fiscalizar", methods=["POST"])  # Se crea una ruta que solo acepta solicitudes de tipo POST.
def fiscalizar():  # Se define la función que contendrá la lógica de la ruta anterior.
    try:  # Se utiliza un bloque try para capturar posibles errores durante la ejecución de la lógica interna.
        # Uso de try y except: permite capturar excepciones (errores) que ocurren en tiempo de ejecución. Por ejemplo, si un archivo no existe o si hay un error al conectarse a la red. Esto evita que el servidor se detenga abruptamente y permite enviar un mensaje de error al cliente.

        datos = request.json  # Se obtienen los datos JSON enviados por el cliente en la solicitud y se convierten en un diccionario de Python.
        if not datos:  # Se valida si no se recibieron datos.
            return jsonify({"error": "No se recibieron datos"}), 400  # Se devuelve un error 400 si no hay datos.

        #Generar TRA
        #tra = generar_tra()

        # Obtener TA
        ta_xml = obtener_ta(CERT, KEY)  # Se obtiene el Ticket de Autenticación (TA) llamando a la función que se comunica con AFIP.
        token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma digital del archivo TA.

        # Consultar último comprobante autorizado
        pto_vta = int(datos.get('punto_venta', 12))  # Se obtiene el punto de venta desde los datos (o se asigna 12 por defecto).
        cbte_tipo = int(datos.get('tipo_comprobante', 1))  # Se obtiene el tipo de comprobante (o se asigna 1 por defecto).
        ultimo = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)  # Se consulta en AFIP cuál fue el último comprobante autorizado.

        siguiente_numero = ultimo['ultimo_numero'] + 1 if ultimo['ultimo_numero'] is not None else 1  # Se calcula el siguiente número de comprobante, sumando 1 al último autorizado o asignando 1 si es el primero.

        # Agregar el número de comprobante a los datos
        datos['cbte_desde'] = siguiente_numero  # Se agrega el campo 'cbte_desde' con el siguiente número de comprobante.
        datos['cbte_hasta'] = siguiente_numero  # Se agrega el campo 'cbte_hasta' con el mismo valor, indicando que es un único comprobante.

        # Construir el XML del comprobante
        try:
            datos_cbte_xml = construir_xml_comprobante(datos)  # Se construye el XML del comprobante con todos los datos. Sí, en este punto, la variable datos contiene lo enviado por el cliente más el campo cbte_desde y cbte_hasta.
        except ValueError as e:
            return jsonify({"error": str(e)}), 400  # Si ocurre un error al construir el XML (p. ej. falta un campo obligatorio), se devuelve un error 400 con el mensaje.

        # Enviar a AFIP
        respuesta_afip = enviar_comprobante(token, sign, CUIT, datos_cbte_xml)  # Se envía el XML a AFIP y se obtiene la respuesta como texto.

        # Intentar parsear la respuesta para ver si hay errores
        try:
            from lxml import etree  # Se importa la librería lxml para procesar XML.
            xml_resp = etree.fromstring(respuesta_afip.encode())  # Se convierte la respuesta en un árbol XML.
            errores = xml_resp.findall(".//Err")  # Se buscan etiquetas de error en la respuesta.
            if errores:  # Si hay errores encontrados en la respuesta:
                mensajes_error = [f"{err.findtext('Code')}: {err.findtext('Msg')}" for err in errores]  # Se construye una lista con los códigos y mensajes de error.
                return jsonify({"error": "Error de AFIP: " + " | ".join(mensajes_error)}), 400  # Se devuelve un error 400 con los detalles encontrados.
        except:  # Si ocurre un error al parsear la respuesta XML, por ejemplo si la respuesta no es XML válido.
            pass  # Se ignora el error y se continúa con la ejecución.

        print("Respuesta cruda de AFIP:", repr(respuesta_afip))  # Se imprime la respuesta cruda de AFIP para debug.
        return jsonify({"xml_afip": respuesta_afip})  # Se devuelve la respuesta de AFIP al cliente.

    except Exception as e:  # Se captura cualquier excepción que no haya sido controlada anteriormente.
        return jsonify({"error": f"Error interno: {str(e)}"}), 500  # Se devuelve un error 500 con el mensaje de la excepción.

@app.route("/")  # Se define la ruta raíz ("/") que sirve la interfaz web.
def interfaz_web():
    return send_from_directory(".", "interface.html")  # Se devuelve el archivo interface.html desde el directorio actual. 

@app.route("/ultimo-comprobante", methods=["GET"])  # Se define una ruta para consultar el último comprobante autorizado.
def ultimo_comprobante():
    try:
        # Obtener parámetros de la consulta
        pto_vta = request.args.get('pto_vta', type=int, default=12)  # Se obtiene el parámetro pto_vta de la URL o se asigna 12.
        cbte_tipo = request.args.get('cbte_tipo', type=int, default=1)  # Se obtiene el parámetro cbte_tipo de la URL o se asigna 1.

        # Obtener TA
        ta_xml = obtener_ta(CERT, KEY)  # Se obtiene el Ticket de Autenticación (TA).
        token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma digital.

        # Consultar último comprobante
        resultado = consultar_ultimo_autorizado(token, sign, CUIT, pto_vta, cbte_tipo)  # Se consulta en AFIP el último comprobante autorizado.

        # Construir respuesta
        respuesta = {
            "ultimo_comprobante": resultado,  # Se incluye la respuesta completa de AFIP.
            "siguiente_numero": resultado['ultimo_numero'] + 1 if resultado['ultimo_numero'] is not None else 1,  # Se calcula el próximo número de comprobante.
            "punto_venta": pto_vta,
            "tipo_comprobante": cbte_tipo
        }

        # Agregar fecha si está disponible
        if resultado.get('fecha_ultimo'):  # Si la fecha del último comprobante está disponible:
            respuesta['fecha_ultimo'] = resultado['fecha_ultimo']  # Se agrega la fecha a la respuesta.

        return jsonify(respuesta)  # Se devuelve la respuesta como JSON.

    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Se devuelve un error 500 en caso de error interno.

@app.route("/estado-ta", methods=["GET"])  # Se define una ruta para consultar el estado del TA (token de autorización).
def estado_ta():
    try:
        # Verificar si existe el archivo TA
        ta_existe = os.path.exists("ta.xml")  # Se verifica si el archivo ta.xml existe.
        ta_info = {  # Se crea un diccionario con la información a devolver.
            "existe": ta_existe,
            "fecha_creacion": None,
            "fecha_expiracion": None,
            "token": None,
            "sign": None
        }

        if ta_existe:  # Si el archivo existe:
            # Leer el TA
            with open("ta.xml") as f:  # Se abre y lee el archivo.
                ta_xml = f.read()

            # Parsear el XML
            root = ET.fromstring(ta_xml)  # Se convierte el XML en un árbol de elementos.

            # Extraer fechas
            exp_time = root.findtext(".//expirationTime")  # Se busca la fecha de expiración.
            gen_time = root.findtext(".//generationTime")  # Se busca la fecha de generación.

            if exp_time:
                ta_info["fecha_expiracion"] = exp_time  # Se guarda la fecha de expiración.
            if gen_time:
                ta_info["fecha_creacion"] = gen_time  # Se guarda la fecha de creación.

            # Extraer token y sign
            token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma.
            ta_info["token"] = token[:10] + "..." if token else None  # Se muestra una parte del token para seguridad.
            ta_info["sign"] = sign[:10] + "..." if sign else None  # Se muestra una parte del sign para seguridad.

            # Verificar si está expirado
            if exp_time:
                exp_datetime = datetime.fromisoformat(exp_time.replace('Z', '+00:00'))  # Se convierte la fecha a objeto datetime.
                ta_info["expirado"] = datetime.now() >= exp_datetime  # Se determina si el TA está expirado.
            else:
                ta_info["expirado"] = True  # Si no hay fecha, se asume que está expirado.

        return jsonify(ta_info)  # Se devuelve la información como JSON.

    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Se devuelve un error 500 en caso de error interno.

@app.route("/regenerar-ta", methods=["POST"])  # Se define una ruta para regenerar el TA manualmente.
def regenerar_ta():
    try:
        # Eliminar TA existente si existe
        if os.path.exists("ta.xml"):  # Se verifica si el archivo ta.xml existe.
            os.remove("ta.xml")  # Se elimina el archivo.

        # Generar nuevo TA
        ta_xml = obtener_ta(CERT, KEY)  # Se genera un nuevo TA.
        token, sign = extraer_token_sign(ta_xml)  # Se extraen el token y la firma.

        return jsonify({  # Se devuelve la información como JSON.
            "mensaje": "TA regenerado exitosamente",
            "token": token[:10] + "...",  # Se muestra parte del token.
            "sign": sign[:10] + "...",  # Se muestra parte del sign.
            "fecha_generacion": datetime.now().isoformat()  # Se muestra la fecha de generación.
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Se devuelve un error 500 en caso de error interno.

if __name__ == "__main__":  # Bloque de inicio para ejecutar la aplicación si se ejecuta como script principal.
    app.run(host="0.0.0.0", port=8080)  # Se inicia el servidor Flask en todas las interfaces de red (0.0.0.0) en el puerto 8080.
