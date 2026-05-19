import serial
import json

def init_serial(port='COM3', baudrate=9600):
    return serial.Serial(port, baudrate, timeout=1)

def read_json(ser):
    try:
        linea = ser.readline().decode('utf-8').strip()

        if not linea:
            return None

        return json.loads(linea)

    except json.JSONDecodeError:
        print("JSON corrupto")
        return None

    except Exception as e:
        print("Error serial:", e)
        return None