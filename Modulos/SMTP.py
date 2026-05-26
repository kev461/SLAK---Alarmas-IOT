import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import pandas as pd
import Modulos.Crear_Excel as Crear_Excel

load_dotenv()

def enviar_mensaje(destinatario, asunto, cuerpo):
    user = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_PASSWORD")

    msg = MIMEText(cuerpo)
    msg['Subject'] = asunto
    msg['From'] = user
    msg['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(user, password)
            server.send_message(msg)
            print(f"¡Correo enviado a {destinatario}!")
    except Exception as e:
        print(f"Error enviando a {destinatario}: {e}")


def ejecutar_envio_alertas():
    """Carga los correos actuales y envía las alertas."""
    dfCorreos = Crear_Excel.obtener_df_correos()

    if dfCorreos.empty:
        print("No hay correos registrados para enviar alertas.")
        return

    listasCorreos = dfCorreos['Correo'].tolist()
    listasNombres = dfCorreos['Nombre'].tolist()

    for nombre, correo in zip(listasNombres, listasCorreos):
        asunto_personalizado = f"Alerta para {nombre}"
        mensaje_personalizado = f"Hola {nombre},\n\n¡Cuidado! Se ha detectado una anomalía en el sistema de alarmas."
        enviar_mensaje(correo, asunto_personalizado, mensaje_personalizado)

def enviar_alerta_peligro(nivel_peligro):
    """Carga los correos actuales y envía las alertas incluyendo el nivel de peligro."""
    dfCorreos = Crear_Excel.obtener_df_correos()

    if dfCorreos.empty:
        print("No hay correos registrados para enviar alertas.")
        return

    listasCorreos = dfCorreos['Correo'].tolist()
    listasNombres = dfCorreos['Nombre'].tolist()

    for nombre, correo in zip(listasNombres, listasCorreos):
        asunto_personalizado = f"Alerta para {nombre} - Nivel {nivel_peligro}"
        mensaje_personalizado = (
            f"Hola {nombre},\n\n"
            f"¡Cuidado! Se ha detectado una anomalía en el sistema de alarmas.\n"
            f"Nivel de peligro detectado: {nivel_peligro}"
        )
        enviar_mensaje(correo, asunto_personalizado, mensaje_personalizado)

if __name__ == '__main__':
    ejecutar_envio_alertas()