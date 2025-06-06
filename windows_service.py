"""
Servicio de Windows para el Fiscalizador AFIP API.

Este script convierte la aplicación Flask en un servicio de Windows que:
1. Se ejecuta automáticamente al iniciar Windows
2. Se puede administrar desde el Administrador de Servicios
3. Mantiene logs tanto en archivo como en el Visor de Eventos de Windows
4. Se reinicia automáticamente si falla

Para instalar el servicio:
    python windows_service.py install
Para iniciar:
    python windows_service.py start
Para detener:
    python windows_service.py stop
Para desinstalar:
    python windows_service.py remove
"""

# Importaciones necesarias para el servicio de Windows
import win32serviceutil  # Utilidades para manejar servicios de Windows
import win32service     # Funcionalidad base de servicios de Windows
import win32event      # Manejo de eventos de Windows
import servicemanager  # Gestión del servicio y logging en el Visor de Eventos
import socket          # Para configuración de timeout
import sys            # Para argumentos de línea de comandos
import os             # Para manejo de rutas y directorios
import logging        # Para logging a archivo
from logging.handlers import RotatingFileHandler  # Para rotación de logs
from app import app   # Importamos nuestra aplicación Flask

class FiscalizadorService(win32serviceutil.ServiceFramework):
    """
    Clase principal que implementa el servicio de Windows.
    Hereda de ServiceFramework para implementar la funcionalidad básica del servicio.
    """
    # Configuración básica del servicio
    _svc_name_ = "FiscalizadorAFIP"           # Nombre interno del servicio
    _svc_display_name_ = "Fiscalizador AFIP API"  # Nombre visible en el Administrador de Servicios
    _svc_description_ = "Servicio API para fiscalización AFIP"  # Descripción del servicio
    _svc_deps_ = ["Tcpip"]  # Dependencia: requiere que el servicio TCP/IP esté activo

    def __init__(self, args):
        """
        Inicialización del servicio.
        Configura el evento de detención y el sistema de logging.
        """
        win32serviceutil.ServiceFramework.__init__(self, args)
        # Evento que se usará para señalar la detención del servicio
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        # Timeout para operaciones de socket
        socket.setdefaulttimeout(60)
        
        # Configuración del sistema de logging
        self._setup_logging()

    def _setup_logging(self):
        """
        Configura el sistema de logging con dos handlers:
        1. Archivo rotativo para logs detallados
        2. Visor de Eventos de Windows para logs del sistema
        """
        # Crear directorio de logs si no existe
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Configurar el logger principal
        self.logger = logging.getLogger('FiscalizadorService')
        self.logger.setLevel(logging.INFO)
        
        # Handler para archivo con rotación (máximo 10 archivos de 10KB)
        file_handler = RotatingFileHandler(
            'logs/fiscalizador_service.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        self.logger.addHandler(file_handler)
        
        # Handler para el Visor de Eventos de Windows
        class WindowsEventHandler(logging.Handler):
            """
            Handler personalizado que envía los logs al Visor de Eventos de Windows.
            Los niveles de log se mapean a los tipos de eventos de Windows:
            - ERROR -> Error
            - WARNING -> Advertencia
            - INFO -> Información
            """
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if record.levelno >= logging.ERROR:
                        servicemanager.LogErrorMsg(msg)
                    elif record.levelno >= logging.WARNING:
                        servicemanager.LogWarningMsg(msg)
                    else:
                        servicemanager.LogInfoMsg(msg)
                except Exception:
                    self.handleError(record)
        
        self.logger.addHandler(WindowsEventHandler())

    def SvcStop(self):
        """
        Se llama cuando el servicio recibe la señal de detención.
        Realiza una detención ordenada del servicio.
        """
        self.logger.info('Deteniendo servicio Fiscalizador AFIP...')
        # Notificar a Windows que el servicio está en proceso de detención
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Señalar el evento de detención
        win32event.SetEvent(self.stop_event)
        self.logger.info('Servicio Fiscalizador AFIP detenido')

    def SvcDoRun(self):
        """
        Método principal que se ejecuta cuando el servicio inicia.
        Configura y ejecuta la aplicación Flask.
        """
        try:
            self.logger.info('Iniciando servicio Fiscalizador AFIP...')
            # Registrar el inicio del servicio en el Visor de Eventos
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            # Configurar la aplicación Flask
            app.logger = self.logger  # Usar el mismo logger
            app.config['SERVER_NAME'] = 'localhost:8080'  # Configurar el nombre del servidor
            
            # Iniciar la aplicación Flask
            self.logger.info('Servicio Fiscalizador AFIP iniciado en http://localhost:8080')
            app.run(host='0.0.0.0', port=8080)  # Escuchar en todas las interfaces
            
        except Exception as e:
            # Loggear cualquier error que ocurra durante la ejecución
            self.logger.error(f'Error en el servicio: {str(e)}')
            servicemanager.LogErrorMsg(f'Error en el servicio: {str(e)}')

def main():
    """
    Punto de entrada principal del script.
    Maneja los argumentos de línea de comandos para instalar/iniciar/detener el servicio.
    """
    if len(sys.argv) == 1:
        # Si no hay argumentos, ejecutar como servicio
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FiscalizadorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Si hay argumentos, procesarlos (install, start, stop, etc.)
        win32serviceutil.HandleCommandLine(FiscalizadorService)

if __name__ == '__main__':
    main() 