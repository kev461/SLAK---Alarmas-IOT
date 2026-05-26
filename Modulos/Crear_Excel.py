import pandas as pd
import logging
from pathlib import Path

# Definimos la ruta de forma global para que otros módulos la usen
BASE_DIR = Path(__file__).resolve().parents[1]
RUTA_EXCEL_CORREOS = BASE_DIR / 'uploads' / 'Correos.xlsx'

def obtener_df_correos():
    """Carga el Excel si existe, si no, devuelve un DataFrame vacío con las columnas correctas."""
    if RUTA_EXCEL_CORREOS.exists():
        return pd.read_excel(RUTA_EXCEL_CORREOS)
    # Si no existe, creamos el molde y lo guardamos de una vez para que el archivo físico exista
    df_nuevo = pd.DataFrame(columns=['Nombre', 'Correo'])
    guardar_df_correos(df_nuevo)
    return df_nuevo

def guardar_df_correos(df: pd.DataFrame):
    """Asegura que la carpeta exista y guarda el DataFrame en el Excel usando openpyxl."""
    RUTA_EXCEL_CORREOS.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(RUTA_EXCEL_CORREOS, index=False, engine='openpyxl')
    return 'La carpeta existe y el DataFrame se ha guardado correctamente.'
