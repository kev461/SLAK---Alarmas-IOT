import sys
import time
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
# INTERCEPTOR DE ALERTAS (Wrapper de MongoDB)
# ======================================================
class ColeccionWrapper:
    def __init__(self, original_coleccion):
        self._original = original_coleccion
        self._ultimo_nivel_alerta = 0
        self._ultimo_tiempo_mensaje = 0.0

    def __getattr__(self, name):
        return getattr(self._original, name)

    def insert_one(self, document, *args, **kwargs):
        # 1. Ejecutar inserción en base de datos
        resultado = self._original.insert_one(document, *args, **kwargs)
        
        # 2. Interceptar nivel de peligro
        nivel = document.get('nivel_peligro')
        if nivel is not None:
            ahora = time.time()
            cooldown_pasado = (ahora - self._ultimo_tiempo_mensaje) >= 60  # 5 minutos = 300 segundos
            ha_subido_peligro = (self._ultimo_nivel_alerta is None) or (nivel > self._ultimo_nivel_alerta)
            
            # Solo intentamos notificar si el nivel actual es de alerta (2 o 3)
            if nivel in [2, 3]:
                if cooldown_pasado or ha_subido_peligro:
                    # Registrar el momento y nivel del mensaje enviado
                    self._ultimo_tiempo_mensaje = ahora
                    self._ultimo_nivel_alerta = nivel
                    
                    # Alertas de Correo (Nivel 2 y 3)
                    try:
                        from Modulos.SMTP import enviar_alerta_peligro
                        print(f"[Alertas] [Correo] Disparando alertas por correo para peligro nivel {nivel} (Razón: Cooldown pasado={cooldown_pasado}, Subió nivel={ha_subido_peligro})...")
                        enviar_alerta_peligro(nivel_peligro=nivel)
                    except Exception as e:
                        print(f"[Alertas] [Error] Error al enviar correos: {e}")
                    
                    # Alertas de Twilio (Nivel 3 únicamente)
                    if nivel == 3:
                        try:
                            from Modulos.twilio_alerta import enviar_alerta_twilio
                            print(f"[Alertas] [Twilio] Disparando alertas por Twilio para peligro nivel {nivel}...")
                            enviar_alerta_twilio(nivel_peligro=nivel)
                        except Exception as e:
                            print(f"[Alertas] [Error] Error al enviar Twilio SMS: {e}")
                else:
                    print(f"[Alertas] [Bloqueado] Alerta omitida por cooldown. Nivel actual: {nivel}, Último enviado: Nivel {self._ultimo_nivel_alerta} hace {ahora - self._ultimo_tiempo_mensaje:.1f}s")
                    
        return resultado

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
        # Envolvemos la colección para interceptar las alertas sin modificar stream_iot_mongo.py
        coleccion = ColeccionWrapper(coleccion)
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a MongoDB: {e}")
        sys.exit(1)

    iniciar_streaming_serial(coleccion, sio_client=sio)