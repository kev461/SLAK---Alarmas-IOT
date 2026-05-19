import pandas as pd
from pathlib import Path
import atexit
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import static.CodePython.Crear_Excel as Crear_Excel
import static.CodePython.Modificación_Correos as Modificación_Correos
import static.CodePython.SMTP as SMTP

from static.CodePython.Firebase import init_firebase
from static.CodePython.leer_serial import init_serial, read_json
from static.CodePython.validador import validar
from static.CodePython.normalizador import normalizar
from datetime import datetime
import time
from firebase_admin import db
# import static.Python.Procesos as Procesos


app = Flask(__name__)



'''
Empieza configuración endpoints
'''
@app.route('/')
def index():
    return render_template('index.html', title='Inicio - Sistema de Alarmas')

@app.route("/leer_firebase")
def leer_firebase():
    data = db.reference("actual").get()
    return render_template("leer_firebase.html", data=data)

@app.route('/administrar_correos', methods=['GET', 'POST'])
def administrar_correos():
    mensaje = None
    # 1. El pipeline inicia aquí: Cargamos los datos más recientes del Excel
    dfCorreos = Crear_Excel.obtener_df_correos()

    if request.method == 'POST':
        action = request.form.get('action') # Identifica si es una acción de agregar o eliminar

        if action == 'add':
            Correo = request.form.get('Correo')
            Nombre = request.form.get('Nombre')
            if Correo and Nombre:
                # 2. El pipeline procesa: Agregamos y guardamos automáticamente
                mensaje, dfCorreos = Modificación_Correos.agregar_correo(dfCorreos, Nombre, Correo)
        elif action == 'delete':
            correo_a_eliminar = request.form.get('correo_a_eliminar')
            if correo_a_eliminar:
                mensaje, dfCorreos = Modificación_Correos.quitar_correo(dfCorreos, correo_a_eliminar)
        elif action == 'send_emails':
            SMTP.ejecutar_envio_alertas()
            mensaje = "Se ha iniciado el proceso de envío de alertas por correo."
        
    return render_template(
        'administrar_correos.html',
        title='Administración de correos',
        # 3. El pipeline muestra: Enviamos los datos actualizados a la tabla HTML
        # Pasamos el DataFrame directamente para construir la tabla con botones en el HTML
        correos_df=dfCorreos, 
        resultado=mensaje
    )

if __name__ == '__main__':
    # No cargamos dfCorreos aquí porque index() lo hace de forma dinámica en cada petición.
    app.run(host='0.0.0.0', debug=True)
    # socketio.run(app, host='0.0.0.0', debug=True)