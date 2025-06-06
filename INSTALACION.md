# Instalación del Fiscalizador AFIP

Este documento describe el proceso de instalación del Fiscalizador AFIP como servicio de Windows.

## Requisitos Previos

- Windows 10 o superior
- Python 3.10 o superior
- Permisos de administrador

## Proceso de Instalación

1. **Preparación**:
   - Descargue el archivo ZIP del repositorio
   - Extraiga el contenido en una carpeta (por ejemplo, `C:\FiscalizadorAFIP`)
   - Abra una terminal como administrador en la carpeta extraída

2. **Instalación Automática**:
   ```batch
   python install_service.py
   ```
   Este script:
   - Instalará las dependencias necesarias
   - Configurará el firewall
   - Instalará y configurará el servicio de Windows
   - Iniciará el servicio automáticamente

3. **Verificación**:
   - Abra el Administrador de Servicios de Windows
   - Busque "Fiscalizador AFIP API"
   - Verifique que el estado sea "En ejecución"
   - La API estará disponible en `http://localhost:8080`

## Comandos Útiles

Para administrar el servicio manualmente:

```batch
# Instalar el servicio
python windows_service.py install

# Iniciar el servicio
python windows_service.py start

# Detener el servicio
python windows_service.py stop

# Desinstalar el servicio
python windows_service.py remove
```

## Solución de Problemas

### Logs
Los logs se encuentran en la carpeta `logs`:
- `fiscalizador_service.log`: Log del servicio
- `installer.log`: Log de la instalación

### Problemas Comunes

1. **Error de permisos**:
   - Asegúrese de ejecutar los comandos como administrador
   - Verifique que el usuario tenga permisos de servicio

2. **Puerto en uso**:
   - Verifique que el puerto 8080 no esté siendo usado por otra aplicación
   - Use `netstat -ano | findstr :8080` para verificar

3. **Servicio no inicia**:
   - Revise los logs en `logs/fiscalizador_service.log`
   - Verifique que Python y las dependencias estén instaladas correctamente

## Para Desarrolladores VFP

La API estará siempre disponible en:
```
http://localhost:8080
```

Ejemplo de uso en VFP:
```vfp
LOCAL lcURL, lcJSON, loHTTP, lcResponse

lcURL = "http://localhost:8080/fiscalizar"
lcJSON = '{"tipo_comprobante": 1, "punto_venta": 12, "tipo_doc": 80, "nro_doc": "20396127823", "imp_total": 1210, "imp_neto": 1000, "imp_iva": 210, "mon_id": "PES", "concepto": 1, "cbte_fch": "20250606"}'

loHTTP = CREATEOBJECT("MSXML2.XMLHTTP")
loHTTP.Open("POST", lcURL, .F.)
loHTTP.setRequestHeader("Content-Type", "application/json")
loHTTP.Send(lcJSON)

lcResponse = loHTTP.responseText
```

## Soporte

Para reportar problemas o solicitar ayuda:
1. Revise los logs en la carpeta `logs`
2. Consulte la documentación en el repositorio
3. Abra un issue en GitHub si el problema persiste 