"""
Módulo: Calcular_peligro.py
Descripción: Calcula el nivel de peligro (1 a 5) de una lectura de sensores IoT.

Estrategia de puntuación:
  - Fuente 1: Sensores individuales con margen de susceptibilidad de laboratorio (×1.7)
  - Fuente 2: Combinaciones sinérgicas de sensores que juntos indican escenarios peligrosos

Soporta dos modos:
  - calcular_peligro_fila(fila): Para UNA fila (dict). Uso en Streaming y en Batch fila a fila.
  - calcular_peligro_batch(df):  Para un DataFrame completo de Pandas. Añade columna 'nivel_peligro'.
"""

import re
import json

# ==============================================================================
# CONFIGURACIÓN DEL MOTOR DE PELIGRO
# Ajusta estos valores para calibrar la sensibilidad del sistema
# ==============================================================================

# Factor de susceptibilidad de laboratorio.
# 1.7 = los sensores disparan con un 30% menos de margen del umbral normal.
FACTOR_SUSCEPTIBILIDAD = 1.8

# --- Umbrales base de sensores individuales ---
# (Condición de activación, puntos base ANTES de aplicar el factor)
UMBRAL_TEMPERATURA_MEDIA  = 35   # °C: Ambiente caliente
UMBRAL_TEMPERATURA_ALTA   = 45   # °C: Riesgo de quemaduras / incendio

PUNTOS_HUMO               = 3.0  # pts: Presencia de humo es señal directa de riesgo
PUNTOS_LLAMA              = 2.0  # pts: Llama detectada
PUNTOS_TEMP_MEDIA         = 1.5  # pts: Temperatura alta (primer umbral)
PUNTOS_TEMP_ALTA          = 3.0  # pts: Temperatura muy alta (segundo umbral, reemplaza la media)
PUNTOS_HUMEDAD_ALTA       = 0.5  # pts: Humedad muy alta (>85%) puede indicar vapor de un incendio
UMBRAL_HUMEDAD_ALTA       = 85   # %RH

PUNTOS_LUZ_ALTA           = 0.5  # pts: Luz muy alta (>50000 Lux) puede indicar fuego brillante
UMBRAL_LUZ_ALTA           = 50000

PUNTOS_MOVIMIENTO         = 0.5  # pts: Movimiento detectado (solo suma si hay otro factor activo)

# --- Puntos extra por combinaciones sinérgicas (independientes de los individuales) ---
PUNTOS_SINERGIA_FUEGO_TOTAL      = 7.0  # Humo + Llama + Temp alta = Incendio declarado
PUNTOS_SINERGIA_INCENDIO_ACTIVO  = 5.0  # Humo + Llama = Incendio activo (sin temp confirmada)
PUNTOS_SINERGIA_FUEGO_SIN_LLAMA  = 3.0  # Humo + Temp alta = Fuego probable sin llama visible
PUNTOS_SINERGIA_LLAMA_CALIENTE   = 3.0  # Llama + Temp alta = Llama con ambiente cálido
PUNTOS_SINERGIA_PRESENCIA_RIESGO = 2.0  # Movimiento + (Humo o Llama) = Persona en zona de riesgo

# --- Bandas de puntuación → Nivel de peligro (1 a 5) ---
# Cada tupla es (puntos_mínimos, nivel)
BANDAS_PELIGRO = [
    (10.0, 3),  # Peligro Crítico (antes 4 y 5)
    (5.0,  2),  # Alerta (antes 2 y 3)
    (0.0,  1),  # Normal
]

# ==============================================================================
# FUNCIÓN CORE: Opera sobre un diccionario con los campos del sensor
# ==============================================================================

def _calcular_puntos(fila: dict) -> float:
    """
    Calcula los puntos de peligro crudos para una lectura de sensores.
    Acepta un diccionario con claves: humo, llama, temperatura, humedad, luz, movimiento.
    Las claves que no existan se asumen como valor 0 (sin novedad).
    """
    # Normalizar: extraer valores con fallback a 0 (tolerante a campos faltantes)
    humo        = int(fila.get('humo', 0))
    llama       = int(fila.get('llama', 0))
    temperatura = float(fila.get('temperatura', 0.0))
    humedad     = float(fila.get('humedad', 0.0))
    luz         = float(fila.get('luz', 0.0))
    movimiento  = int(fila.get('movimiento', 0))
    
    puntos = 0.0
    hay_factor_primario = False  # Para decidir si el movimiento suma

    # ----------------------------------------------------------------
    # FUENTE 1: Sensores Individuales × Factor de Susceptibilidad
    # ----------------------------------------------------------------
    if humo == 1:
        puntos += PUNTOS_HUMO * FACTOR_SUSCEPTIBILIDAD
        hay_factor_primario = True

    if llama == 1:
        puntos += PUNTOS_LLAMA * FACTOR_SUSCEPTIBILIDAD
        hay_factor_primario = True

    # La temperatura usa el umbral más alto que supere (no suma ambos)
    if temperatura > UMBRAL_TEMPERATURA_ALTA:
        puntos += PUNTOS_TEMP_ALTA * FACTOR_SUSCEPTIBILIDAD
        hay_factor_primario = True
    elif temperatura > UMBRAL_TEMPERATURA_MEDIA:
        puntos += PUNTOS_TEMP_MEDIA * FACTOR_SUSCEPTIBILIDAD
        hay_factor_primario = True

    if humedad > UMBRAL_HUMEDAD_ALTA:
        puntos += PUNTOS_HUMEDAD_ALTA * FACTOR_SUSCEPTIBILIDAD

    if luz > UMBRAL_LUZ_ALTA:
        puntos += PUNTOS_LUZ_ALTA * FACTOR_SUSCEPTIBILIDAD

    # Movimiento solo suma si ya hay otro factor activo (evita falsos positivos de personas)
    if movimiento == 1 and hay_factor_primario:
        puntos += PUNTOS_MOVIMIENTO * FACTOR_SUSCEPTIBILIDAD

    # ----------------------------------------------------------------
    # FUENTE 2: Combinaciones Sinérgicas (puntos adicionales)
    # ----------------------------------------------------------------
    temp_alta = temperatura > UMBRAL_TEMPERATURA_MEDIA  # Umbral de sinergia (más permisivo)
    
    # La más grave se evalúa primero y excluye las demás de su categoría
    if humo == 1 and llama == 1 and temp_alta:
        puntos += PUNTOS_SINERGIA_FUEGO_TOTAL
    elif humo == 1 and llama == 1:
        puntos += PUNTOS_SINERGIA_INCENDIO_ACTIVO
    else:
        # Las sinergias parciales pueden acumularse entre sí
        if humo == 1 and temp_alta:
            puntos += PUNTOS_SINERGIA_FUEGO_SIN_LLAMA
        if llama == 1 and temp_alta:
            puntos += PUNTOS_SINERGIA_LLAMA_CALIENTE

    # Sinergia de presencia en zona de riesgo (independiente de las anteriores)
    if movimiento == 1 and (humo == 1 or llama == 1):
        puntos += PUNTOS_SINERGIA_PRESENCIA_RIESGO

    return round(puntos, 2)


def _puntos_a_nivel(puntos: float) -> int:
    """Mapea una puntuación cruda a un nivel de peligro del 1 al 5."""
    for umbral, nivel in BANDAS_PELIGRO:
        if puntos >= umbral:
            return nivel
    return 1  # Fallback de seguridad


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
    Interfaz simple: recibe un dict y devuelve solo el nivel de peligro (int 1-5).
    Útil para integrar en el pipeline de Procesos.py al recibir dato del Arduino.
    """
    puntos = _calcular_puntos(fila)
    return _puntos_a_nivel(puntos)


# ==============================================================================
# DEMO: Prueba rápida del módulo si se ejecuta directamente
# ==============================================================================

if __name__ == '__main__':
    print("=" * 55)
    print("  DEMO — Motor de Peligro SLAK IoT (Factor ×1.7)")
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
        print(f"   Puntos: {resultado['puntos']:.2f}  →  Nivel de Peligro: {'⚠️ ' * resultado['nivel_peligro']} ({resultado['nivel_peligro']}/5)")