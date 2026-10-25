"""Constantes de la integración iTranvías A Coruña."""

DOMAIN = "itranvias_coruna"
PLATFORMS = ["sensor"]

API_URL = "https://itranvias.com/queryitr_v3.php"
# Cadena "dato" literal verificada para el catálogo (func=7). No es un número de línea.
CATALOGO_DATO = "20160101T000000_gl_0_20160101T000000"

CONF_PARADA = "parada"
CONF_INTERVALO = "intervalo"
CONF_MAX_LLEGADAS = "max_llegadas"

# Valor inicial configurable; NO es una frecuencia autorizada por el proveedor.
DEFAULT_INTERVALO = 60
MIN_INTERVALO = 30
MAX_INTERVALO = 600
DEFAULT_MAX_LLEGADAS = 4
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
