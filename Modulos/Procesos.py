import time
import pandas as pd
import Modulos.SMTP as SMTP
from Modulos.validador import validar
from Modulos.normalizador import normalizar

# --- CONFIGURACIÓN DE SEGURIDAD ---
USA_MONGO = False  # Cambia a True cuando quieras conectar con Atlas
MONGO_URI = "mongodb+srv://tu_usuario:<db_password>@cluster0.mongodb.net/"
UMBRAL = 80

def procesar_dato_arduino(data):
    """
    Centraliza la lógica de validación, normalización y decisiones.
    """
    if not validar(data):
        return None, False

    dato_procesado = normalizar(data)
    
    requiere_accion = False
    if dato_procesado.get('valor', 0) > UMBRAL:
        requiere_accion = True
        
    return dato_procesado, requiere_accion

def obtener_ultimo_dato_mongo():
    """
    Lee el último registro de MongoDB o devuelve una simulación si está desactivado.
    """
    if not USA_MONGO:
        # Devuelve datos de prueba para que la interfaz web funcione sin Mongo
        return {
            "temp": "--", 
            "hum": "--", 
            "gas": "DESCONECTADO", 
            "llama": "NO", 
            "sonido": "MOCK", 
            "peligro": "MODO_OFFLINE"
        }

    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        db = client['tu_base_datos']
        coleccion = db['tu_coleccion']
        return coleccion.find_one(sort=[('_id', -1)])
    except Exception as e:
        print(f"Error de conexión con MongoDB: {e}")
        return None

def guardar_en_mongo(data):
    """
    Sube un dato a MongoDB solo si está activado.
    """
    if not USA_MONGO:
        return
    
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        client['tu_base_datos']['tu_coleccion'].insert_one(data)
    except Exception as e:
        print(f"Error guardando en Mongo: {e}")