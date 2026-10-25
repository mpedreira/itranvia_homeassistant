"""Cliente de la API web de iTranvías (A Coruña).

API sin documentación oficial ni garantía de estabilidad. Solo se usan las dos
operaciones comprobadas: func=0 (llegadas de una parada) y func=7 (catálogo).
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_URL, CATALOGO_DATO


class ItranviasError(Exception):
    """Error al consultar o interpretar la API."""

    def __init__(self, mensaje: str, bloqueado: bool = False) -> None:
        super().__init__(mensaje)
        self.bloqueado = bloqueado


# ---------------------------------------------------------------- utilidades
def _int(valor: Any) -> int | None:
    if isinstance(valor, bool):
        return None
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def parse_tiempo(valor: Any) -> tuple[int | None, bool]:
    """Interpreta el campo "tiempo" -> (minutos, menor_que_1).

    "<1" -> (None, True): se conserva como "<1", NO como 0 exacto.
    Número -> (n, False). Cualquier otra cosa -> (None, False) = desconocido.
    """
    if valor is None:
        return None, False
    texto = str(valor).strip()
    if texto.startswith("<"):
        return None, True
    n = _int(texto)
    if n is None or n < 0:
        return None, False
    return n, False


def clave_orden(bus: dict[str, Any]) -> tuple[int, int]:
    """Primero "<1", luego minutos ascendentes, al final desconocidos."""
    if bus["menor_que_1"]:
        return (0, 0)
    if bus["minutos"] is not None:
        return (1, bus["minutos"])
    return (2, 0)


def texto_tiempo(bus: dict[str, Any]) -> str:
    if bus["menor_que_1"]:
        return "<1"
    if bus["minutos"] is not None:
        return str(bus["minutos"])
    return "?"


# ------------------------------------------------------------------ llegadas
def parse_llegadas(data: Any) -> dict[int, list[dict[str, Any]]]:
    """{id_linea: [buses ordenados]} con todos los vehículos de la parada.

    Solo aparecen las líneas con vehículos activos en ese momento.
    Cada bus: vehiculo, tiempo (texto original), minutos, menor_que_1,
    distancia (string de la API -> int, presumiblemente metros), estado (sin
    interpretar) y ult_parada (id de parada).
    """
    if not isinstance(data, dict) or data.get("resultado") != "OK":
        raise ItranviasError("Respuesta inesperada de la API")

    buses_nodo = data.get("buses")
    lineas = buses_nodo.get("lineas") if isinstance(buses_nodo, dict) else None
    resultado: dict[int, list[dict[str, Any]]] = {}
    for grupo in lineas or []:
        if not isinstance(grupo, dict):
            continue
        id_linea = _int(grupo.get("linea"))
        if id_linea is None:
            continue
        buses = []
        for b in grupo.get("buses") or []:
            if not isinstance(b, dict):
                continue
            minutos, menor_1 = parse_tiempo(b.get("tiempo"))
            buses.append(
                {
                    "vehiculo": _int(b.get("bus")),
                    "tiempo": b.get("tiempo"),
                    "minutos": minutos,
                    "menor_que_1": menor_1,
                    "distancia": _int(b.get("distancia")),
                    "estado": b.get("estado"),
                    "ult_parada": _int(b.get("ult_parada")),
                }
            )
        if buses:
            resultado[id_linea] = sorted(buses, key=clave_orden)
    return resultado


# ------------------------------------------------------------------ catálogo
def _color(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    c = valor.strip().lstrip("#").upper()
    if len(c) == 6 and all(ch in "0123456789ABCDEF" for ch in c):
        return c
    return None


def _nodo_catalogo(data: dict[str, Any]) -> dict[str, Any] | None:
    """Localiza iTranvias.actualizacion (anidado o con la clave con punto)."""
    for ruta in (("iTranvias", "actualizacion"), ("iTranvias.actualizacion",)):
        nodo: Any = data
        for clave in ruta:
            nodo = nodo.get(clave) if isinstance(nodo, dict) else None
        if isinstance(nodo, dict):
            return nodo
    nodo = data.get("actualizacion")
    return nodo if isinstance(nodo, dict) else None


def parse_catalogo(data: Any) -> dict[str, Any]:
    """Reduce el catálogo a lo necesario.

    Devuelve {"fecha", "lineas": {id: {nombre, origen, destino, color}},
    "paradas": {id: {nombre, enlaces: [ids de línea]}}}.
    """
    if not isinstance(data, dict):
        raise ItranviasError("Catálogo inesperado")
    nodo = _nodo_catalogo(data)
    if nodo is None:
        raise ItranviasError("Catálogo sin iTranvias.actualizacion")

    lineas: dict[int, dict[str, Any]] = {}
    for l in nodo.get("lineas") or []:
        if not isinstance(l, dict):
            continue
        id_linea = _int(l.get("id"))
        nombre = l.get("lin_comer")
        if id_linea is None or not nombre:
            continue
        lineas[id_linea] = {
            "nombre": str(nombre),
            "origen": l.get("nombre_orig"),
            "destino": l.get("nombre_dest"),
            "color": _color(l.get("color")),
        }

    paradas: dict[int, dict[str, Any]] = {}
    for p in nodo.get("paradas") or []:
        if not isinstance(p, dict):
            continue
        id_parada = _int(p.get("id"))
        if id_parada is None:
            continue
        enlaces = [e for e in (_int(x) for x in p.get("enlaces") or []) if e is not None]
        paradas[id_parada] = {"nombre": p.get("nombre") or "", "enlaces": enlaces}

    if not lineas or not paradas:
        raise ItranviasError("Catálogo vacío")
    return {"fecha": nodo.get("fecha"), "lineas": lineas, "paradas": paradas}


# ------------------------------------------------------------------ peticiones
async def _get_json(
    session: aiohttp.ClientSession, params: dict[str, Any], timeout: int
) -> Any:
    try:
        async with asyncio.timeout(timeout):
            async with session.get(API_URL, params=params) as resp:
                if resp.status in (403, 429, 503):
                    raise ItranviasError(f"HTTP {resp.status}", bloqueado=True)
                resp.raise_for_status()
                return await resp.json(content_type=None)
    except ItranviasError:
        raise
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        raise ItranviasError(f"Error de conexión o de formato: {err}") from err


async def async_get_llegadas(
    session: aiohttp.ClientSession, parada: int
) -> dict[int, list[dict[str, Any]]]:
    data = await _get_json(session, {"func": 0, "dato": parada}, 10)
    return parse_llegadas(data)


async def async_get_catalogo(session: aiohttp.ClientSession) -> dict[str, Any]:
    data = await _get_json(session, {"func": 7, "dato": CATALOGO_DATO}, 30)
    return parse_catalogo(data)
