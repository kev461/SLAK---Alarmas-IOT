import serial
import os
from pathlib import Path
from dotenv import load_dotenv

# Configuración de rutas para cargar variables de entorno
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Configuración del puerto (ajustar según el dispositivo, e.g., /dev/rfcomm0 o COM3)
PUERTO_SERIAL = os.getenv('IOT_SERIAL_PORT', '/dev/rfcomm0')
BAUDRATE = 115200 

def procesar_y_enviar(luz, ventilador):
    """
    Recibe estados: luz (0,1,2), ventilador (0,1).
    Forma la cadena solicitada y la envía al HC-05.
    """
    # Formato: [Luz][Ventilador]1
    cadena_mando = f"{luz}{ventilador}1"
    print(f"[enviar_datos_createpi] Enviando al HC-05: {cadena_mando}")

    try:
        ser = serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=1)
        ser.write(cadena_mando.encode())
        ser.close()
        return True
    except Exception as e:
        print(f"[enviar_datos_createpi] Error Serial: {e}")
        return False
