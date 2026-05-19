import sys
from pathlib import Path
from flask import Flask
from flask_socketio import SocketIO
import threading
import time

# 1. Configuración de rutas con Pathlib (Sin usar OS)
# APP_DIR es 'flask_alarmas', BASE_DIR es la raíz del proyecto
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# Importar rutas y procesos (Ahora que el path está configurado)
from flask_alarmas.routes import registrar_rutas
import Modulos.Procesos as Procesos

app = Flask(__name__, 
            template_folder=str(APP_DIR / 'templates'),
            static_folder=str(APP_DIR / 'static'))

socketio = SocketIO(app)

# Configuración del intervalo de refresco (segundos)
INTERVALO_REFRESCO = 5 

def background_mongo_watcher():
    """
    Hilo de fondo que consulta MongoDB periódicamente y 
    actualiza la web mediante Sockets.
    """
    print(f"Iniciando vigilante de MongoDB (Refresco cada {INTERVALO_REFRESCO}s)...")
    while True:
        try:
            # Consultar último dato
            ultimo_dato = Procesos.obtener_ultimo_dato_mongo() 
            
            if ultimo_dato:
                socketio.emit('nuevo_dato', ultimo_dato)
                
        except Exception as e:
            print(f"Error en vigilante de Mongo: {e}")
            
        time.sleep(INTERVALO_REFRESCO)

# Registrar las rutas
registrar_rutas(app)

if __name__ == '__main__':
    # Iniciar el vigilante en segundo plano
    threading.Thread(target=background_mongo_watcher, daemon=True).start()
    
    print("Iniciando Servidor Web Independiente (Pathlib Mode)...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
