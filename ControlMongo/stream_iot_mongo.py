"""
Módulo: stream_iot_mongo.py
Descripción: Pipeline de Streaming IoT — Arduino → Python → MongoDB Atlas

Flujo:
  1. Leer una línea/JSON crudo que llega del Arduino por Serial (o simular)
  2. Calcular el nivel de peligro (1-3) con el motor de Calcular_peligro
  3. Envía los datos de peligro al Arduino por Serial
  4. Guardar el registro enriquecido en MongoDB Atlas
  5. Repetir indefinidamente (bucle de escucha)

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
PUERTO_SERIAL = '/dev/rfcomm0'
# Con la interfaz bluetooth configurada se usa esta dirección
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

# Variable para rastrear el último nivel de peligro enviado a la placa
_ultimo_nivel: int | None = None

def procesar_linea(linea_cruda: str, coleccion) -> dict:
    """
    Procesa una línea cruda del Arduino:
    1. Parsea y normaliza los datos del sensor (tolerante a JSON o CSV)
    2. Calcula el nivel de peligro (1-5) con el motor ×1.7
    3. Añade timestamp
    4. Guarda en MongoDB
    5. Retorna el documento guardado
    """
    linea = linea_cruda.strip()
    if not linea:
        return None

    # Calcular peligro (el módulo detecta formato automáticamente)
    resultado = calcular_peligro_streaming(linea)

    # Construir documento enriquecido para MongoDB
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
    # Enviar nivel de peligro a la placa solo si cambia respecto al último enviado
    global _ultimo_nivel
    if _ultimo_nivel != resultado['nivel_peligro']:
        enviado = enviar_nivel_peligro_placa(resultado['nivel_peligro'])
        if enviado:
            _ultimo_nivel = resultado['nivel_peligro']
    else:
        # Nivel no cambió, no enviar
        pass

def enviar_nivel_peligro_placa(nivel_peligro: int) -> bool:
    """Envía el nivel de peligro a la placa vía serial.

    Args:
        nivel_peligro: Nivel de peligro calculado (1, 2 o 3).

    Returns:
        bool: True si se envió correctamente, False en caso de error o si la
        comunicación serial no está disponible.
    """
    # Verificar disponibilidad de pyserial
    if not SERIAL_DISPONIBLE:
        print("[Serial] pyserial no está disponible. No se envía nivel de peligro.")
        return False
    # Validar nivel
    if nivel_peligro not in ETIQUETAS_NIVEL:
        print(f"[Serial] Nivel de peligro inválido: {nivel_peligro}")
        return False
    try:
        ser = serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=TIMEOUT_S)
        ser.write(str(nivel_peligro).encode())
        ser.flush()
        print(f"[Serial] Nivel {nivel_peligro} enviado a placa.")
        return True
    except serial.SerialException as e:
        print(f"[Serial] Error al enviar nivel de peligro: {e}")
        return False
    finally:
        try:
            ser.close()
        except Exception:
            pass

def procesar_linea_dashboard(linea_cruda: str, sio_client=None) -> dict:
    """
    Procesa una línea del Arduino y la inyecta DIRECTAMENTE al Dashboard de Flask.
    A diferencia de 'procesar_linea', esta función NO guarda en MongoDB para
    evitar latencia o duplicidad, enfocándose solo en la visualización en vivo.
    """
    linea = linea_cruda.strip()
    if not linea:
        return None

    # 1. Calcular peligro (normalización y motor x1.7)
    resultado = calcular_peligro_streaming(linea)

    # Construir documento optimizado para JSON
    documento = {
        **resultado['datos_sensor'],
        'puntos_peligro':  resultado['puntos'],
        'nivel_peligro':   resultado['nivel_peligro'],
        'fecha_registro':  datetime.utcnow().isoformat(), # Formato string para compatibilidad JSON
        'fuente':          'arduino_realtime',
    }

    # 3. Emitir evento al Dashboard de Flask (evento 'nuevo_dato' esperado por app.py)
    if sio_client and sio_client.connected:
        try:
            sio_client.emit('nuevo_dato', documento)
        except Exception as e:
            print(f"[Dashboard] Error de inyección de datos: {e}")
    
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
        print(f"[Serial] Puerto abierto. Escuchando Arduino...")
    except serial.SerialException as e:
        print(f"[Serial] Error al abrir puerto: {e}")
        return

    print("\nPresiona Ctrl+C para detener el streaming.\n")
    try:
        while True:
            linea_bytes = ser.readline()
            if linea_bytes:
                linea = linea_bytes.decode('utf-8', errors='replace').strip()
                if linea:
                    # FLUJO 1: Persistencia e Historial (MongoDB)
                    procesar_linea(linea, coleccion)
                    
                    # FLUJO 2: Visualización en Tiempo Real (Dashboard Flask)
                    if sio_client:
                        procesar_linea_dashboard(linea, sio_client)
    except KeyboardInterrupt:
        print("\n[Serial] Streaming detenido por el usuario.")
    finally:
        ser.close()

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

if __name__ == '__main__':
    print("SLAK IoT — Streaming Serial → MongoDB | Socket")

    # Inicializar cliente de Sockets para el Dashboard
    sio = None
    if SIO_DISPONIBLE:
        sio = socketio.Client()
        try:
            # Dirección del servidor Flask (ajusta si corre en otro host/puerto)
            sio.connect('http://localhost:5000')
            print("[SocketIO] Conectado al Dashboard de Flask.")
        except Exception:
            print("[SocketIO] No se pudo conectar al Dashboard. Los datos solo se guardarán en MongoDB.")
            sio = None

    try:
        coleccion = conectar_mongo()
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a MongoDB: {e}")
        sys.exit(1)
