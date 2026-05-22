import sys
from pathlib import Path

# Configuración de rutas para encontrar los módulos
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from ControlMongo.stream_iot_mongo import iniciar_streaming_serial, conectar_mongo, SIO_DISPONIBLE
try:
    import socketio
except ImportError:
    socketio = None # Para evitar errores si no está instalado

# ======================================================
# MOTOR DE DATOS (SERIAL -> PROCESOS -> MONGO)
# ======================================================
if __name__ == '__main__':
    print("=" * 55)
    print("  SLAK IoT — Iniciando Motor de Datos")
    print("=" * 55)
    
    sio = None
    if SIO_DISPONIBLE and socketio:
        sio = socketio.Client()
        try:
            sio.connect('http://127.0.0.1:5000') # Asegúrate que Flask esté corriendo en este puerto
            print("[SocketIO] ✅ Conectado al Dashboard de Flask.")
        except Exception:
            print("[SocketIO] ⚠️ No se pudo conectar al Dashboard. Los datos solo se guardarán en MongoDB.")
            sio = None

    try:
        coleccion = conectar_mongo()
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a MongoDB: {e}")
        sys.exit(1)

    iniciar_streaming_serial(coleccion, sio_client=sio)