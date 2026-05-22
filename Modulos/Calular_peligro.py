"""
Módulo: Calcular_peligro.py
Descripción: Determina el nivel de peligro (1 a 3) basado en reglas directas.

Lógica de Score Final:
  - Nivel 3: Gas + Llama detectados simultáneamente.
  - Nivel 2: Gas detectado O Llama detectada por más de X segundos.
  - Nivel 1: Temperatura > 27°C o estado Normal.

Soporta dos modos:
  - calcular_peligro_fila(fila): Para UNA fila (dict). Uso en Streaming y en Batch fila a fila.
  - calcular_peligro_batch(df):  Para un DataFrame completo de Pandas. Añade columna 'nivel_peligro'.
"""

import re
import json
import time

# ==============================================================================
# CONFIGURACIÓN DEL MOTOR DE PELIGRO
# Ajusta estos valores para calibrar la sensibilidad del sistema
# ==============================================================================
BANDAS_PELIGRO = [
    (3.0, 3),  # Peligro Crítico
    (2.0, 2),  # Alerta
    (0.0,  1),  # Normal
]

UMBRAL_TEMPERATURA_NIVEL_1 = 27.0
UMBRAL_SEGUNDOS_LLAMA      = 5.0

# Variable para rastrear cuánto tiempo lleva activa la llama (Uso en tiempo real)
_llama_inicio_time = None

# ==============================================================================
# FUNCIÓN CORE: Opera sobre un diccionario con los campos del sensor
# ==============================================================================

def _calcular_puntos(fila: dict) -> float:
    """
    Calcula los puntos de peligro crudos para una lectura de sensores.
    Acepta un diccionario con claves: humo, llama, temperatura, humedad, luz, movimiento.
    Las claves que no existan se asumen como valor 0 (sin novedad).
    """
    global _llama_inicio_time

    # Normalizar: extraer valores con fallback a 0 (tolerante a campos faltantes)
    humo        = int(fila.get('humo', 0)) or int(fila.get('gas', 0)) # Mapeo gas/humo
    llama       = int(fila.get('llama', 0))
    temperatura = float(fila.get('temperatura', 0.0))

    # 1. Regla Crítica: Gas y Llama -> Peligro 3
    if humo == 1 and llama == 1:
        return 3.0

    # 2. Regla Alerta: Gas detectado -> Peligro 2
    if humo == 1:
        return 2.0

    # 3. Regla Alerta: Llama persistente por más de X segundos -> Peligro 2
    if llama == 1:
        if _llama_inicio_time is None:
            _llama_inicio_time = time.time()
        
        duracion = time.time() - _llama_inicio_time
        if duracion > UMBRAL_SEGUNDOS_LLAMA:
            return 2.0
    else:
        _llama_inicio_time = None

    # 4. Regla Normal/Base: Temperatura > 27 -> Peligro 1
    if temperatura > UMBRAL_TEMPERATURA_NIVEL_1:
        return 1.0

    # Por defecto es Nivel 1 (Normal)
    return 1.0


def _puntos_a_nivel(puntos: float) -> int:
    """Como el 'puntos' ahora es el nivel directamente, solo retornamos el entero."""
    return int(puntos)


# ==============================================================================
# MODO 1: STREAMING — Una sola lectura (dict, JSON string o línea CSV cruda)
# ==============================================================================

def calcular_peligro_streaming(entrada) -> dict:
    """
    Calcula el nivel de peligro para UNA sola lectura proveniente de un Arduino.
    
    Acepta múltiples formatos de entrada de forma tolerante:
      - dict:  {'temperatura': 36.5, 'humo': 1, ...}
      - str JSON: '{"temperatura": 36.5, "humo": 1}'
      - str CSV línea: '1,0,1,5000,38.5,70.2' (en el orden del CSV)
    
    Retorna un dict con la lectura normalizada + 'puntos' + 'nivel_peligro'.
    """
    fila = {}
    
    if isinstance(entrada, dict):
        # Ya es un diccionario, listo para usar
        fila = entrada
        
    elif isinstance(entrada, str):
        entrada = entrada.strip()
        
        # Intentar parsear como JSON primero
        try:
            fila = json.loads(entrada)
        except json.JSONDecodeError:
            # Intentar como línea CSV (valores separados por coma)
            # Orden esperado del CSV del proyecto: humo,movimiento,llama,luz,temperatura,humedad
            partes = [p.strip() for p in entrada.split(',')]
            if len(partes) >= 6:
                try:
                    fila = {
                        'humo':        partes[0],
                        'movimiento':  partes[1],
                        'llama':       partes[2],
                        'humedad':     partes[3],
                        'temperatura': partes[4],
                        'luz':     partes[5],
                    }
                except (IndexError, ValueError):
                    fila = {}
            else:
                # Línea incompleta o formato desconocido: calcular con lo que venga
                # Intentar extraer valores numéricos por regex
                numeros = re.findall(r'[-+]?\d*\.?\d+', entrada)
                if len(numeros) >= 1:
                    # Solo temperatura por ejemplo
                    fila = {'temperatura': numeros[0]}
    else:
        raise TypeError(f"Tipo de entrada no soportado: {type(entrada)}")

    puntos = _calcular_puntos(fila)
    nivel  = _puntos_a_nivel(puntos)
    
    return {
        'datos_sensor': {
            'humo':        int(fila.get('humo', 0)),
            'movimiento':  int(fila.get('movimiento', 0)),
            'llama':       int(fila.get('llama', 0)),
            'luz':         float(fila.get('luz', 0)),
            'temperatura': float(fila.get('temperatura', 0)),
            'humedad':     float(fila.get('humedad', 0)),
        },
        'puntos':        puntos,
        'nivel_peligro': nivel,
    }


# ==============================================================================
# MODO 2: BATCH — DataFrame de Pandas (procesamiento del CSV completo)
# ==============================================================================

def calcular_peligro_batch(df):
    """
    Añade una columna 'nivel_peligro' y 'puntos_peligro' a un DataFrame de Pandas.
    Procesa todas las filas eficientemente sin bucles lentos (usa apply).
    
    El DataFrame debe tener las columnas del CSV:
    humo, movimiento, llama, luz, temperatura, humedad
    
    Retorna el mismo DataFrame con las dos columnas nuevas añadidas.
    """
    df = df.copy()  # No mutar el original
    
    # Calcular puntos para cada fila (apply es eficiente para lógica compleja)
    df['puntos_peligro'] = df.apply(
        lambda row: _calcular_puntos(row.to_dict()), axis=1
    )
    
    # Mapear puntos al nivel de peligro 1-5
    df['nivel_peligro'] = df['puntos_peligro'].apply(_puntos_a_nivel)
    
    return df


# ==============================================================================
# MODO 3 (Alias simple): Función genérica para cualquier dict
# ==============================================================================

def calcular_peligro_fila(fila: dict) -> int:
    """
    Interfaz simple: recibe un dict y devuelve el nivel de peligro (int 1-3).
    Útil para integrar en el pipeline de Procesos.py al recibir dato del Arduino.
    """
    puntos = _calcular_puntos(fila)
    return _puntos_a_nivel(puntos)


# ==============================================================================
# DEMO: Prueba rápida del módulo si se ejecuta directamente
# ==============================================================================

if __name__ == '__main__':
    print("=" * 55)
    print("  DEMO — Motor de Peligro SLAK IoT (Reglas Directas)")
    print("=" * 55)

    casos_prueba = [
        {
            "nombre": "Lectura normal (Noche fría)",
            "dato": {"humo": 0, "movimiento": 0, "llama": 0, "luz": 200, "temperatura": 18.5, "humedad": 75.0}
        },
        {
            "nombre": "Temperatura alta sin humo",
            "dato": {"humo": 0, "movimiento": 0, "llama": 0, "luz": 500, "temperatura": 38.0, "humedad": 60.0}
        },
        {
            "nombre": "Humo detectado solo",
            "dato": {"humo": 1, "movimiento": 0, "llama": 0, "luz": 300, "temperatura": 22.0, "humedad": 80.0}
        },
        {
            "nombre": "Humo + Movimiento (alerta presencia)",
            "dato": {"humo": 1, "movimiento": 1, "llama": 0, "luz": 300, "temperatura": 26.0, "humedad": 78.0}
        },
        {
            "nombre": "Humo + Llama + Temperatura alta",
            "dato": {"humo": 1, "movimiento": 1, "llama": 1, "luz": 80000, "temperatura": 47.0, "humedad": 90.0}
        },
        {
            "nombre": "Streaming: JSON string incompleto (solo temp y humo)",
            "dato": '{"temperatura": 42, "humo": 1}'
        },
        {
            "nombre": "Streaming: Línea CSV cruda",
            "dato": "1,1,1,75000,48.0,88.0"
        },
    ]

    for caso in casos_prueba:
        if isinstance(caso['dato'], dict):
            resultado = calcular_peligro_streaming(caso['dato'])
        else:
            resultado = calcular_peligro_streaming(caso['dato'])
        
        print(f"\n📍 {caso['nombre']}")
        print(f"   Score Final: {resultado['puntos']} → Nivel: {'⚠️ ' * resultado['nivel_peligro']} ({resultado['nivel_peligro']}/3)")