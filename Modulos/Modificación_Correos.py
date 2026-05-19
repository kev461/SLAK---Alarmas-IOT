import pandas as pd
from pathlib import Path
import Modulos.Crear_Excel as Crear_Excel

# Calculamos la ruta absoluta del archivo para evitar errores de "archivo no encontrado"

def agregar_correo(dfCorreos:pd.DataFrame ,nombre: str, correo: str):
    """
    Añade un nuevo par (Nombre, Correo) a la lista.
    """
    # Aseguramos que la carpeta 'uploads' exista
    # ruta_excel_correos.parent.mkdir(parents=True, exist_ok=True)

    # Verificamos si el correo ya está en la lista para no repetirlo
    if correo in dfCorreos['Correo'].values:
        Mensaje=(f"El correo '{correo}' ya existe en la lista. No se agregará.")
        return Mensaje,dfCorreos

    # Creamos el nuevo registro con el nombre y correo asociados
    nuevo_registro = pd.DataFrame({'Nombre': [nombre], 'Correo': [correo]})
    dfCorreos = pd.concat([dfCorreos, nuevo_registro], ignore_index=True)

    Crear_Excel.guardar_df_correos(dfCorreos)
    Mensaje=(f"Registrado: {nombre} ({correo})")
    return Mensaje,dfCorreos


def quitar_correo(dfCorreos:pd.DataFrame,correo: str):
    """
    Elimina de la lista el elemento que coincida con el correo indicado.
    """

    if correo not in dfCorreos['Correo'].values:
        Mensaje=(f"No se encontró el correo '{correo}' para eliminar.")
        return Mensaje,dfCorreos


    # Filtramos el DataFrame para conservar todo menos el correo que queremos quitar
    dfCorreos_actualizado = dfCorreos[dfCorreos['Correo'] != correo]

    Crear_Excel.guardar_df_correos(dfCorreos_actualizado)
    Mensaje = (f"Correo '{correo}' eliminado de la lista.")
    return Mensaje, dfCorreos_actualizado
