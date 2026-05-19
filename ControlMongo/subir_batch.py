import os
import re
import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# Asegurar que el módulo de peligro sea accesible desde cualquier CWD
BASE_DIR_INIT = Path(__file__).resolve().parent.parent
if str(BASE_DIR_INIT) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_INIT))
from Modulos.Calular_peligro import calcular_peligro_batch

# 1. Definir rutas relativas al proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / '.env'
csv_path = BASE_DIR / 'uploads' / 'datos_sensores.csv'

# 2. Cargar variables de entorno del archivo .env
load_dotenv(dotenv_path)

MONGO_URI = os.getenv('IOT_MONGO_URI')
MONGO_DB = os.getenv('IOT_MONGO_DB')
MONGO_COLECCION = os.getenv('IOT_MONGO_COLECCION')

print("=== CONFIGURACIÓN DE CONEXIÓN ===")
print(f"Base de Datos: {MONGO_DB}")
print(f"Colección:     {MONGO_COLECCION}")
print("=================================\n")

def limpiar_valor_float(valor):
    """
    Limpia cadenas que puedan contener texto no deseado (como '4000q') 
    y las convierte a float de forma segura.
    """
    if pd.isna(valor):
        return -9999
    
    # Convertir a string y limpiar espacios
    val_str = str(valor).strip()
    
    # Extraer solo dígitos, puntos decimales y signos negativos
    val_limpio = re.sub(r'[^\d]', '', val_str)
    
    try:
        return float(val_limpio)
    except ValueError:
        return -9999

def ejecutar_subida_batch():
    if not csv_path.exists():
        print(f"Error: No se encontró el archivo CSV en la ruta: {csv_path}")
        return

    print(f"1. Leyendo el archivo CSV: {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error al leer el archivo CSV: {e}")
        return

    print("2. Limpiando y normalizando los datos para MongoDB...")
    
    # Normalización de Binarios (humo, movimiento, llama)
    df['humo'] = df['humo'].fillna(-9999).astype(int)
    df['movimiento'] = df['movimiento'].fillna(-9999).astype(int)
    df['llama'] = df['llama'].fillna(-9999).astype(int)
    
    # Normalización de Long/Entero (luz)
    df['luz'] = df['luz'].fillna(-9999).astype(int)
    
    # Normalización y Limpieza de Floats (temperatura, humedad)
    df['temperatura'] = df['temperatura'].apply(limpiar_valor_float)
    df['humedad'] = df['humedad'].apply(limpiar_valor_float)
    
    # Añadimos un campo timestamp con la fecha y hora actual UTC
    df['fecha_registro'] = datetime.utcnow()

    # Calcular nivel de peligro para cada fila
    print("   -> Calculando nivel de peligro por fila (motor ×1.7)...")
    df = calcular_peligro_batch(df)
    
    # Resumen de distribución de niveles
    dist = df['nivel_peligro'].value_counts().sort_index()
    for nivel, cantidad in dist.items():
        barra = '⚠️ ' * nivel
        print(f"      Nivel {nivel} {barra}: {cantidad} registros")

    # Convertimos el DataFrame a una lista de diccionarios (JSON)
    registros = df.to_dict(orient='records')
    print(f"   -> Se prepararon {len(registros)} registros para subir.")

    print("\n3. Conectando a MongoDB Atlas...")
    try:
        # Se crea el cliente de pymongo
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Validar conexión ejecutando un comando básico
        client.admin.command('ping')
        print("   -> Conexión exitosa con MongoDB Atlas.")
        
        db = client[MONGO_DB]
        coleccion = db[MONGO_COLECCION]
        
        print(f"4. Insertando {len(registros)} registros en la colección '{MONGO_COLECCION}'...")
        resultado = coleccion.insert_many(registros)
        
        print("\n=================================")
        print(f"¡ÉXITO COMPLETO!")
        print(f"Se insertaron correctamente {len(resultado.inserted_ids)} documentos.")
        print("=================================")
        
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un fallo en el proceso: {e}")
        print("Asegúrate de que tu dirección IP esté habilitada en MongoDB Atlas Network Access.")

if __name__ == '__main__':
    ejecutar_subida_batch()