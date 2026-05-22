"""
Módulo: stream_iot_mongo.py
Descripción: Pipeline de Streaming IoT — Arduino → Python → MongoDB Atlas

Flujo:
  1. Leer una línea/JSON crudo que llega del Arduino por Serial (o simular)
  2. Calcular el nivel de peligro (1-5) con el motor de Calcular_peligro
  3. Guardar el registro enriquecido en MongoDB Atlas
  4. Repetir indefinidamente (bucle de escucha)

Formatos de entrada tolerados del Arduino:
  - JSON:    {"temperatura": 36.5, "humo": 1, "llama": 0, "movimiento": 1, "luz": 3000, "humedad": 72.5}
  - CSV row: 1,0,1,5000,38.5,70.2   (orden: humo,movimiento,llama,luz,temperatura,humedad)
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Asegurar acceso a los módulos del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from Modulos.Calular_peligro import calcular_peligro_streaming

# Cargar variables de entorno
load_dotenv(BASE_DIR / '.env')

MONGO_URI     = os.getenv('IOT_MONGO_URI')
MONGO_DB      = os.getenv('IOT_MONGO_DB')
MONGO_COL     = os.getenv('IOT_MONGO_COLECCION')

# Intentar importar PySerial para lectura real del Arduino
try:
    import serial
    SERIAL_DISPONIBLE = True
except ImportError:
    SERIAL_DISPONIBLE = False

# Intentar importar socketio para la inyección directa al dashboard
try:
    import socketio
    SIO_DISPONIBLE = True
except ImportError:
    SIO_DISPONIBLE = False

# ==============================================================================
# CONFIGURACIÓN DEL PUERTO SERIAL
# Cambia estos valores según tu entorno
# ==============================================================================
PUERTO_SERIAL = '/dev/rfcomm0'  # Linux. En Windows sería 'COM3', 'COM4', etc.
BAUDRATE      = 115200
TIMEOUT_S     = 2            # Segundos de espera por una línea

# ==============================================================================
# CONEXIÓN A MONGODB (singleton de sesión)
# ==============================================================================

def conectar_mongo():
    """Establece y retorna la colección de MongoDB. Lanza excepción si falla."""
    client    = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')  # Validar conexión
    coleccion = client[MONGO_DB][MONGO_COL]
    coleccion.create_index([("fecha_registro", -1)])  # Índice para consultas históricas
    print(f"[MongoDB] Conectado → {MONGO_DB} / {MONGO_COL}")
    return coleccion

# ==============================================================================
# PROCESAMIENTO DE UNA LÍNEA (el corazón del streaming)
# ==============================================================================

ETIQUETAS_NIVEL = {
    1: "NORMAL",          # Antes Nivel 1 y 2
    2: "ALERTA",          # Antes Nivel 3 y 4
    3: "PELIGRO CRÍTICO", # Antes Nivel 5
}

def procesar_linea(resultado: dict, coleccion) -> dict:
    """
    Guarda en MongoDB el resultado ya calculado.
    Mantiene exactamente el mismo formato de documento que tenías antes.
    """
    # Construir documento enriquecido para MongoDB (Mismo formato original)
    documento = {
        **resultado['datos_sensor'],          # Todos los campos del sensor
        'puntos_peligro':  resultado['puntos'],
        'nivel_peligro':   resultado['nivel_peligro'],
        'fecha_registro':  datetime.utcnow(),
        'fuente':          'arduino_serial',
    }

    # Guardar en MongoDB
    coleccion.insert_one(documento)

    # Log en consola
    etiqueta = ETIQUETAS_NIVEL.get(resultado['nivel_peligro'], '?')
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"Temp:{documento['temperatura']:.1f}°C | "
        f"Humo:{documento['humo']} | "
        f"Llama:{documento['llama']} | "
        f"Peligro: {resultado['puntos']:.1f}pts → Nivel {resultado['nivel_peligro']} {etiqueta}"
    )

    return documento

def procesar_linea_dashboard(resultado: dict, sio_client=None) -> dict:
    """
    Inyecta el resultado al Dashboard de Flask.
    Convierte la fecha a string ISO para que el WebSocket (JSON) no falle.
    """
    # Construir documento optimizado para JSON
    documento = {
        **resultado['datos_sensor'],
        'puntos_peligro':  resultado['puntos'],
        'nivel_peligro':   resultado['nivel_peligro'],
        # Usamos ISO format aquí porque JSON no soporta objetos datetime de Python
        'fecha_registro':  datetime.utcnow().isoformat(), 
        'fuente':          'arduino_realtime',
    }

    # 3. Emitir evento al Dashboard de Flask (evento 'nuevo_dato' esperado por app.py)
    if sio_client and sio_client.connected:
        try:
            sio_client.emit('nuevo_dato', documento)
            print(f"[Dashboard] 🚀 Datos inyectados en tiempo real (Nivel {resultado['nivel_peligro']})")
        except Exception as e:
            print(f"[Dashboard] ❌ Error de inyección: {e}")
    
    return documento

# ==============================================================================
# MODO REAL: Lectura desde Arduino vía Serial
# ==============================================================================

def iniciar_streaming_serial(coleccion, sio_client=None):
    """
    Bucle de escucha real del Arduino.
    Lee líneas del puerto serial indefinidamente y las procesa.
    """
    if not SERIAL_DISPONIBLE:
        raise ImportError("pyserial no está instalado. Ejecuta: pip install pyserial")

    print(f"[Serial] Abriendo puerto {PUERTO_SERIAL} a {BAUDRATE} baudios...")
    try:
        ser = serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=TIMEOUT_S)
        print(f"[Serial] ✅ Puerto abierto. Escuchando Arduino...")
    except serial.SerialException as e:
        print(f"[Serial] ❌ Error al abrir puerto: {e}")
        return

    print("\nPresiona Ctrl+C para detener el streaming.\n")
    try:
        while True:
            linea_bytes = ser.readline()
            if linea_bytes:
                linea = linea_bytes.decode('utf-8', errors='replace').strip()
                if linea:
                    # CALCULO ÚNICO: Se hace una vez para asegurar consistencia
                    resultado = calcular_peligro_streaming(linea)

                    # FLUJO 1: Guardar en MongoDB Atlas (Tal cual como estaba)
                    procesar_linea(resultado, coleccion)
                    
                    # FLUJO 2: Enviar al Dashboard (Sin afectar a Mongo)
                    if sio_client:
                        procesar_linea_dashboard(resultado, sio_client)
    except KeyboardInterrupt:
        print("\n[Serial] Streaming detenido por el usuario.")
    finally:
        ser.close()

# ==============================================================================
# MODO SIMULACIÓN: Para probar sin Arduino físico
# ==============================================================================

DATOS_SIMULACION = [
    '{"humo": 0, "movimiento": 0, "llama": 0, "luz": 450, "temperatura": 20.5, "humedad": 68.0}',
    '{"humo": 0, "movimiento": 1, "llama": 0, "luz": 800, "temperatura": 24.2, "humedad": 72.0}',
    '{"humo": 1, "movimiento": 0, "llama": 0, "luz": 1200, "temperatura": 29.0, "humedad": 78.0}',
    '{"humo": 1, "movimiento": 1, "llama": 0, "luz": 2000, "temperatura": 33.0, "humedad": 81.0}',
    '{"humo": 1, "movimiento": 1, "llama": 1, "luz": 55000, "temperatura": 44.0, "humedad": 87.0}',
    # Formato CSV crudo (como podría enviarlo un Arduino simple)
    '0,0,0,300,19.0,65.0',
    '1,1,1,78000,49.5,91.0',
]

def iniciar_streaming_simulado(coleccion, sio_client=None, intervalo_s: float = 2.0):
    """
    Simula un streaming del Arduino con datos de prueba.
    Útil para desarrollo y demos sin hardware físico.
    """
    print("[Simulación] Modo de prueba sin Arduino físico.")
    print(f"[Simulación] Enviando {len(DATOS_SIMULACION)} lecturas con pausa de {intervalo_s}s...")
    if sio_client: print("[Simulación] Inyectando también al Dashboard.")
    try:
        for i, linea in enumerate(DATOS_SIMULACION):
            procesar_linea(linea, coleccion)
            if sio_client:
                procesar_linea_dashboard(linea, sio_client)
            time.sleep(intervalo_s)
        print("\n[Simulación] ✅ Todas las lecturas procesadas.")
    except KeyboardInterrupt:
        print("\n[Simulación] Detenido por el usuario.")

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

if __name__ == '__main__':
    print("=" * 55)
    print("  SLAK IoT — Pipeline de Streaming Serial → MongoDB")
    print("=" * 55)

    # Inicializar cliente de Sockets para el Dashboard
    sio = None
    if SIO_DISPONIBLE:
        sio = socketio.Client()
        try:
            # Dirección del servidor Flask (ajusta si corre en otro host/puerto)
            sio.connect('http://localhost:5000')
            print("[SocketIO] ✅ Conectado al Dashboard de Flask.")
        except Exception:
            print("[SocketIO] ⚠️ No se pudo conectar al Dashboard. Los datos solo se guardarán en MongoDB.")
            sio = None

    try:
        coleccion = conectar_mongo()
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a MongoDB: {e}")
        sys.exit(1)

    # Detectar si hay Arduino físico disponible
    # Para cambiar a modo real: cambia a iniciar_streaming_serial(coleccion)
    # iniciar_streaming_simulado(coleccion, sio_client=sio, intervalo_s=1.0)
    iniciar_streaming_serial(coleccion, sio_client=sio)
