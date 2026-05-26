from pathlib import Path
from dotenv import dotenv_values
from twilio.rest import Client

# Cargar variables de entorno usando pathlib y dotenv_values (sin usar os)
env_path = Path(__file__).resolve().parent.parent / '.env'
config = dotenv_values(env_path)

def enviar_alerta_twilio(nivel_peligro: int):
    """
    Envía una alerta SMS usando la API de Twilio si el nivel de peligro es 3.
    """
    if nivel_peligro != 3:
        # Solo se envía si el nivel de peligro es exactamente 3
        return

    account_sid = config.get("twilio_sid")
    auth_token = config.get("auth_token")
    phone_number = config.get("verified_number")

    print(f"[Twilio] Iniciando proceso de alerta por peligro critico (Nivel {nivel_peligro})...")

    if not all([account_sid, auth_token, phone_number]):
        print("[Twilio] [Advertencia] Faltan configurar las variables de entorno en tu .env:")
        print("         twilio_sid, auth_token, verified_number")
        return

    try:
        client = Client(account_sid, auth_token)
        mensaje = (
            f"⚠️ ALERTA SLAK IoT: Peligro Critico detectado (Nivel {nivel_peligro}).\n"
            f"Se ha detectado presencia de humo/gas y llama de manera simultanea."
        )
        # Se envía desde el número verificado de Twilio hacia el mismo para alertar al administrador
        message = client.messages.create(
            body=mensaje,
            from_=phone_number,
            to=phone_number
        )
        print(f"[Twilio] [Exito] Alerta SMS enviada correctamente. Message SID: {message.sid}")
    except Exception as e:
        print(f"[Twilio] [Error] Error al enviar mensaje usando Twilio SDK: {e}")

if __name__ == '__main__':
    # Prueba del módulo
    enviar_alerta_twilio(3)
