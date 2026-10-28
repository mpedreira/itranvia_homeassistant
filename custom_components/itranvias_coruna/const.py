"""Constantes de la integración iTranvías A Coruña."""
import math

DOMAIN = "itranvias_coruna"
PLATFORMS = ["sensor"]

API_URL = "https://itranvias.com/queryitr_v3.php"
# Cadena "dato" literal verificada para el catálogo (func=7). No es un número de línea.
CATALOGO_DATO = "20160101T000000_gl_0_20160101T000000"

CONF_PARADA = "parada"
CONF_INTERVALO = "intervalo"
CONF_MAX_LLEGADAS = "max_llegadas"
CONF_PAUSA_DESDE = "pausa_desde"
CONF_PAUSA_HASTA = "pausa_hasta"

# Valor inicial configurable; NO es una frecuencia autorizada por el proveedor.
DEFAULT_INTERVALO = 180
MIN_INTERVALO = 90
MAX_INTERVALO = 600
DEFAULT_MAX_LLEGADAS = 4
# Pausa nocturna: no se consulta entre estas horas (hora local de Home Assistant).
# Si desde y hasta son iguales, no hay pausa.
DEFAULT_PAUSA_DESDE = "00:30:00"
DEFAULT_PAUSA_HASTA = "05:30:00"
MAX_MAX_LLEGADAS = 20

# Catálogo: se refresca cada 24 h; tras un fallo se espera más (1 h, 2 h... hasta 24 h).
CATALOGO_REFRESCO = 24 * 3600
CATALOGO_ESPERA_ERROR = 3600
# Si llega una línea que el catálogo no conoce, se permite un refresco como mucho cada hora.
CATALOGO_ESPERA_URGENTE = 3600

# Tras fallos de llegadas o bloqueo (403/429/503) se espacian las consultas.
ESPERA_MINIMA_BLOQUEO = 300
ESPERA_MAXIMA = 900

STORAGE_VERSION = 1

# Límites de consultas que el proveedor comunica en sus respuestas 429
# (1 por segundo, 4 por minuto, 199 por hora, 1999 por día). El de un día es el que
# manda con polling continuo: se deja un margen para reinicios y recargas.
LIMITE_DIA = 1999
MARGEN_LIMITE = 0.8
ESCALONADO_ARRANQUE = 2  # segundos entre paradas al arrancar (límite: 1 por segundo)


def a_minutos(valor: str) -> int:
    """"HH:MM" o "HH:MM:SS" -> minutos desde medianoche."""
    h, m = (int(x) for x in str(valor).split(":")[:2])
    return h * 60 + m


def en_pausa(minuto: int, desde: str, hasta: str) -> bool:
    """True si el minuto del día cae en la pausa [desde, hasta). Admite pausas que cruzan medianoche."""
    d, h = a_minutos(desde), a_minutos(hasta)
    if d == h:
        return False
    if d < h:
        return d <= minuto < h
    return minuto >= d or minuto < h


def horas_activas(desde: str, hasta: str) -> float:
    """Horas al día en las que se consulta (24 menos la pausa)."""
    d, h = a_minutos(desde), a_minutos(hasta)
    if d == h:
        return 24.0
    return (1440 - (h - d) % 1440) / 60


def consultas_dia(paradas: list[tuple[int, float]]) -> float:
    """Consultas diarias estimadas. Cada parada es (intervalo en s, horas activas al día)."""
    return sum(horas * 3600 / max(i, 1) for i, horas in paradas)


def intervalo_minimo(n_paradas: int, horas: float = 24.0) -> int:
    """Intervalo (s) mínimo por parada para no pasar del margen del límite diario."""
    return math.ceil(max(n_paradas, 1) * horas * 3600 / (LIMITE_DIA * MARGEN_LIMITE))


def excede_limite(paradas: list[tuple[int, float]]) -> bool:
    return consultas_dia(paradas) > LIMITE_DIA * MARGEN_LIMITE
