import sys
from pathlib import Path

# Configuración de rutas para encontrar los módulos
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import Modulos.Controlador_Alarmas as Motor

# ======================================================
# MOTOR DE DATOS (SERIAL -> PROCESOS -> MONGO)
# ======================================================
if __name__ == '__main__':
    # Arranca el proceso de fondo que gestiona el hardware y los datos
    # No conoce nada de la interfaz web (Flask)
    Motor.iniciar_motor_datos()