import time
import Modulos.Procesos as Procesos
from Modulos.leer_serial import init_serial, read_json

def iniciar_motor_datos():
    """
    Bucle principal del Motor de Datos:
    Recibir -> Procesar -> Reenviar -> Subir a Mongo
    """
    try:
        ser = init_serial('COM3', 9600)
    except Exception as e:
        print(f"Hardware no disponible: {e}")
        ser = None
        
    print("Motor de datos iniciado (Pipeline: Serial -> Procesos -> Mongo)")
    
    while True:
        # 1. RECIBIR
        if ser:
            data = read_json(ser)
        else:
            time.sleep(5) # Simulación lenta para no saturar consola
            data = {"sensor_id": "MOCK_01", "valor": 25.5, "estado": "OK"}

        if not data:
            continue

        # 2. PROCESAR (Lógica en Procesos.py)
        # Aquí se valida y se decide qué hacer
        dato_procesado, requiere_accion = Procesos.procesar_dato_arduino(data)
        
        if not dato_procesado:
            continue

        # 3. REENVIAR al Arduino (Si la lógica lo requiere)
        if requiere_accion and ser:
            ser.write(b'ALERTA_ON\n')
            print(">>> Comando de acción enviado al Arduino")

        # 4. SUBIR A MONGO (Esta lógica se puede llamar desde Procesos.py)
        # Procesos.guardar_en_mongo(dato_procesado)

        print(f"Dato Procesado: {dato_procesado}")
        time.sleep(1)
