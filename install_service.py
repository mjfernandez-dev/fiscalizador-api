"""
Script de instalación para el Fiscalizador AFIP API.

Este script automatiza el proceso de instalación del servicio de Windows:
1. Verifica permisos de administrador
2. Instala dependencias de Python
3. Configura el firewall de Windows
4. Instala y configura el servicio

Para ejecutar:
    python install_service.py (como administrador)
"""

import os
import sys
import subprocess  # Para ejecutar comandos del sistema
import winreg     # Para acceso al registro de Windows
import ctypes     # Para verificar permisos de administrador
import logging
from logging.handlers import RotatingFileHandler

def is_admin():
    """
    Verifica si el script se está ejecutando con permisos de administrador.
    
    Returns:
        bool: True si tiene permisos de administrador, False en caso contrario
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def setup_logging():
    """
    Configura el sistema de logging para el instalador.
    Crea dos handlers:
    1. Archivo rotativo para logs detallados
    2. Consola para feedback inmediato al usuario
    
    Returns:
        logging.Logger: Logger configurado
    """
    # Crear directorio de logs si no existe
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    # Configurar el logger
    logger = logging.getLogger('Installer')
    logger.setLevel(logging.INFO)
    
    # Handler para archivo con rotación (máximo 5 archivos de 10KB)
    file_handler = RotatingFileHandler(
        'logs/installer.log',
        maxBytes=10240,
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    ))
    logger.addHandler(file_handler)
    
    # Handler para consola (mensajes simples)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    return logger

def install_python_dependencies():
    """
    Instala las dependencias de Python listadas en requirements.txt.
    Usa pip para instalar los paquetes necesarios.
    
    Raises:
        subprocess.CalledProcessError: Si la instalación falla
    """
    logger.info("Instalando dependencias de Python...")
    try:
        # Ejecutar pip install con el archivo requirements.txt
        subprocess.run([
            sys.executable,  # Python actual
            "-m",           # Ejecutar como módulo
            "pip",         # Módulo pip
            "install",     # Comando install
            "-r",          # Instalar desde archivo
            "requirements.txt"
        ], check=True)     # Verificar que el comando fue exitoso
        logger.info("Dependencias instaladas correctamente")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al instalar dependencias: {str(e)}")
        raise

def configure_firewall():
    """
    Configura el firewall de Windows para permitir el tráfico al puerto 8080.
    Crea reglas tanto de entrada como de salida.
    
    Raises:
        subprocess.CalledProcessError: Si la configuración falla
    """
    logger.info("Configurando firewall...")
    try:
        # Agregar regla de entrada (tráfico entrante al puerto 8080)
        subprocess.run([
            "netsh", 
            "advfirewall", 
            "firewall", 
            "add", 
            "rule",
            "name=FiscalizadorAFIP",  # Nombre de la regla
            "dir=in",                 # Dirección: entrada
            "action=allow",           # Acción: permitir
            "protocol=TCP",           # Protocolo: TCP
            "localport=8080"          # Puerto: 8080
        ], check=True)
        
        # Agregar regla de salida (tráfico saliente del puerto 8080)
        subprocess.run([
            "netsh", 
            "advfirewall", 
            "firewall", 
            "add", 
            "rule",
            "name=FiscalizadorAFIP",
            "dir=out",                # Dirección: salida
            "action=allow",
            "protocol=TCP",
            "localport=8080"
        ], check=True)
        
        logger.info("Firewall configurado correctamente")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al configurar firewall: {str(e)}")
        raise

def install_service():
    """
    Instala y configura el servicio de Windows.
    Realiza tres pasos:
    1. Instala el servicio
    2. Configura el inicio automático
    3. Inicia el servicio
    
    Raises:
        subprocess.CalledProcessError: Si la instalación falla
    """
    logger.info("Instalando servicio Fiscalizador AFIP...")
    try:
        # Obtener rutas absolutas
        service_path = os.path.abspath("windows_service.py")
        python_path = sys.executable
        
        # Paso 1: Instalar el servicio
        subprocess.run([
            python_path,
            service_path,
            "install"
        ], check=True)
        
        # Paso 2: Configurar inicio automático
        subprocess.run([
            python_path,
            service_path,
            "update",
            "--startup", "auto"  # Configurar para iniciar automáticamente
        ], check=True)
        
        # Paso 3: Iniciar el servicio
        subprocess.run([
            python_path,
            service_path,
            "start"
        ], check=True)
        
        logger.info("Servicio instalado y iniciado correctamente")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al instalar el servicio: {str(e)}")
        raise

def main():
    """
    Función principal del instalador.
    Coordina todo el proceso de instalación:
    1. Configura logging
    2. Verifica permisos
    3. Instala dependencias
    4. Configura firewall
    5. Instala servicio
    """
    global logger
    logger = setup_logging()
    
    logger.info("Iniciando instalación del Fiscalizador AFIP...")
    
    # Verificar permisos de administrador
    if not is_admin():
        logger.error("Este script requiere permisos de administrador")
        print("Por favor, ejecute este script como administrador")
        sys.exit(1)
    
    try:
        # Paso 1: Instalar dependencias
        install_python_dependencies()
        
        # Paso 2: Configurar firewall
        configure_firewall()
        
        # Paso 3: Instalar servicio
        install_service()
        
        # Instalación completada
        logger.info("Instalación completada exitosamente")
        print("\nInstalación completada exitosamente!")
        print("El servicio Fiscalizador AFIP está instalado y ejecutándose")
        print("La API está disponible en: http://localhost:8080")
        
    except Exception as e:
        # Manejar cualquier error durante la instalación
        logger.error(f"Error durante la instalación: {str(e)}")
        print(f"\nError durante la instalación: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 