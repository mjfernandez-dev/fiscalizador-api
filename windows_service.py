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
Para debug:
    python windows_service.py debug
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
import threading      # Para ejecutar Flask en un hilo separado
import time          # Para el bucle principal
from logging.handlers import RotatingFileHandler  # Para rotación de logs
from app import app   # Importamos nuestra aplicación Flask
from waitress import serve  # Servidor de producción para Windows
from datetime import datetime  # Para registrar la fecha y hora de errores

class DebugService:
    """
    Versión simplificada del servicio para modo debug.
    No depende del sistema de servicios de Windows.
    """
    def __init__(self):
        self.running = True
        self.server_thread = None
        self._setup_logging()

    def _setup_logging(self):
        """Configura el sistema de logging para modo debug."""
        # Crear directorio de logs si no existe
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Configurar el logger principal
        self.logger = logging.getLogger('FiscalizadorService')
        self.logger.setLevel(logging.INFO)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s'
        ))
        self.logger.addHandler(console_handler)
        
        # Handler para archivo
        file_handler = RotatingFileHandler(
            'logs/fiscalizador_service.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        self.logger.addHandler(file_handler)

    def _run_server(self):
        """Ejecuta el servidor Flask en un hilo separado."""
        try:
            self.logger.info('Iniciando servidor Flask en http://localhost:8080')
            serve(app, host='0.0.0.0', port=8080, threads=4)
        except Exception as e:
            self.logger.error(f'Error en el servidor Flask: {str(e)}')
            self.running = False

    def stop(self):
        """Detiene el servicio."""
        self.logger.info('Deteniendo servicio Fiscalizador AFIP...')
        self.running = False
        self.logger.info('Servicio Fiscalizador AFIP detenido')

    def run(self):
        """Ejecuta el servicio en modo debug."""
        try:
            self.logger.info('Iniciando servicio Fiscalizador AFIP en modo debug...')
            
            # Configurar la aplicación Flask
            app.logger = self.logger
            
            # Iniciar el servidor Flask en un hilo separado
            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Bucle principal
            while self.running:
                if not self.server_thread.is_alive():
                    self.logger.error('El servidor Flask se detuvo inesperadamente')
                    self.running = False
                    break
                time.sleep(5)
                
        except Exception as e:
            self.logger.error(f'Error en el servicio: {str(e)}')
            self.running = False

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
        try:
            # Configurar logging lo más temprano posible
            self._setup_logging()
            self.logger.info('Inicializando servicio Fiscalizador AFIP...')
            
            # Inicializar el framework del servicio
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.logger.info('Framework del servicio inicializado')
            
            # Evento que se usará para señalar la detención del servicio
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.logger.info('Evento de detención creado')
            
            # Flag para controlar el bucle principal
            self.running = True
            
            # Timeout para operaciones de socket
            socket.setdefaulttimeout(60)
            self.logger.info('Timeout de socket configurado')
            
            # Thread para el servidor Flask
            self.server_thread = None
            
            self.logger.info('Inicialización del servicio completada')
            
        except Exception as e:
            # Intentar loggear el error incluso si el logging no está configurado
            try:
                self.logger.error(f'Error en la inicialización del servicio: {str(e)}')
            except:
                # Si falla el logging, al menos escribir en un archivo
                with open('service_error.log', 'a') as f:
                    f.write(f'{datetime.now()}: Error en la inicialización del servicio: {str(e)}\n')
            raise  # Re-lanzar la excepción para que Windows sepa que falló

    def _setup_logging(self):
        """
        Configura el sistema de logging con dos handlers:
        1. Archivo rotativo para logs detallados
        2. Visor de Eventos de Windows para logs del sistema
        """
        try:
            # Crear directorio de logs si no existe
            if not os.path.exists('logs'):
                os.makedirs('logs')
                
            # Configurar el logger principal
            self.logger = logging.getLogger('FiscalizadorService')
            self.logger.setLevel(logging.INFO)
            
            # Limpiar handlers existentes
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
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
            self.logger.info('Sistema de logging configurado')
            
        except Exception as e:
            # Si falla la configuración del logging, escribir en un archivo
            with open('service_error.log', 'a') as f:
                f.write(f'{datetime.now()}: Error configurando logging: {str(e)}\n')
            raise  # Re-lanzar la excepción

    def _run_server(self):
        """
        Ejecuta el servidor Flask en un hilo separado.
        """
        try:
            self.logger.info('Iniciando servidor Flask en http://localhost:8080')
            serve(app, host='0.0.0.0', port=8080, threads=4)
        except Exception as e:
            self.logger.error(f'Error en el servidor Flask: {str(e)}')
            self.running = False

    def SvcStop(self):
        """
        Se llama cuando el servicio recibe la señal de detención.
        Realiza una detención ordenada del servicio.
        """
        self.logger.info('Deteniendo servicio Fiscalizador AFIP...')
        # Notificar a Windows que el servicio está en proceso de detención
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Detener el bucle principal
        self.running = False
        # Señalar el evento de detención
        win32event.SetEvent(self.stop_event)
        self.logger.info('Servicio Fiscalizador AFIP detenido')

    def SvcDoRun(self):
        """
        Método principal que se ejecuta cuando el servicio inicia.
        Mantiene un bucle principal mientras el servicio está activo.
        """
        try:
            # Notificar a Windows que el servicio está iniciando
            self.logger.info('Notificando inicio del servicio a Windows...')
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            
            self.logger.info('Iniciando servicio Fiscalizador AFIP...')
            # Registrar el inicio del servicio en el Visor de Eventos
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            # Configurar la aplicación Flask
            self.logger.info('Configurando aplicación Flask...')
            app.logger = self.logger  # Usar el mismo logger
            
            # Iniciar el servidor Flask en un hilo separado
            self.logger.info('Iniciando servidor Flask en hilo separado...')
            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.daemon = True  # El hilo se detendrá cuando el programa principal termine
            self.server_thread.start()
            
            # Esperar un momento para asegurarnos de que el servidor inició
            self.logger.info('Esperando inicio del servidor...')
            time.sleep(2)
            
            if not self.server_thread.is_alive():
                self.logger.error('El servidor Flask no pudo iniciar')
                raise Exception('El servidor Flask no pudo iniciar')
            
            # Notificar a Windows que el servicio está en ejecución
            self.logger.info('Notificando a Windows que el servicio está en ejecución...')
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            
            # Bucle principal del servicio
            self.logger.info('Iniciando bucle principal del servicio...')
            while self.running:
                # Verificar el estado del servidor
                if not self.server_thread.is_alive():
                    self.logger.error('El servidor Flask se detuvo inesperadamente')
                    self.running = False
                    break
                
                # Esperar un poco antes de la siguiente verificación
                # Usar WaitForSingleObject para responder a señales de Windows
                rc = win32event.WaitForSingleObject(self.stop_event, 5000)  # 5 segundos
                if rc == win32event.WAIT_OBJECT_0:
                    # Se recibió señal de detención
                    self.logger.info('Se recibió señal de detención')
                    break
                
        except Exception as e:
            # Loggear cualquier error que ocurra durante la ejecución
            self.logger.error(f'Error en el servicio: {str(e)}')
            servicemanager.LogErrorMsg(f'Error en el servicio: {str(e)}')
            self.running = False
            # Notificar a Windows que el servicio se detuvo por error
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        finally:
            # Asegurarse de que el servicio se detenga limpiamente
            self.logger.info('Deteniendo servicio...')
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)

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
    elif len(sys.argv) > 1 and sys.argv[1] == 'debug':
        # Modo debug: usar la versión simplificada
        print("Iniciando en modo debug...")
        service = DebugService()
        try:
            service.run()
        except KeyboardInterrupt:
            print("\nDeteniendo servicio (Ctrl+C)...")
            service.stop()
    else:
        # Si hay otros argumentos, procesarlos (install, start, stop, etc.)
        win32serviceutil.HandleCommandLine(FiscalizadorService)

if __name__ == '__main__':
    main() 