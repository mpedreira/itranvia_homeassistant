"""Catálogo de líneas y paradas: una sola copia compartida, en caché."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import ItranviasError, async_get_catalogo
from .const import (
    CATALOGO_ESPERA_ERROR,
    CATALOGO_ESPERA_URGENTE,
    CATALOGO_REFRESCO,
    DOMAIN,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class CatalogoManager:
    """Descarga el catálogo una vez, lo guarda en disco y lo refresca cada 24 h."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.catalogo")
        self.lineas: dict[int, dict[str, Any]] = {}
        self.paradas: dict[int, dict[str, Any]] = {}
        self.fecha: str | None = None
        self.actualizado = None
        self._lock = asyncio.Lock()
        self._cargado = False
        self._en_curso = False
        self._fallos = 0
        self._proximo_intento = 0.0
        self._proximo_urgente = 0.0

    @property
    def disponible(self) -> bool:
        return bool(self.lineas and self.paradas)

    # -- consulta ---------------------------------------------------------
    def nombre_linea(self, id_linea: int) -> str:
        return (self.lineas.get(id_linea) or {}).get("nombre") or "?"

    def info_linea(self, id_linea: int) -> dict[str, Any]:
        return self.lineas.get(id_linea) or {}

    def nombre_parada(self, id_parada: int | None) -> str | None:
        if id_parada is None:
            return None
        return (self.paradas.get(id_parada) or {}).get("nombre") or None

    def tiene_linea(self, id_linea: int) -> bool:
        return id_linea in self.lineas

    def enlaces(self, id_parada: int) -> list[int]:
        return list((self.paradas.get(id_parada) or {}).get("enlaces") or [])

    # -- carga ------------------------------------------------------------
    async def async_asegurar(self) -> None:
        """Garantiza que hay catálogo (disco o descarga). Lanza ItranviasError."""
        async with self._lock:
            if not self._cargado:
                await self._cargar_disco()
                self._cargado = True
                if self.disponible:
                    # Caché del disco: la próxima revisión será pasada su antigüedad.
                    self._proximo_intento = time.monotonic() + self._segundos_restantes()
            if not self.disponible:
                await self._descargar()

    def _segundos_restantes(self) -> float:
        if self.actualizado is None:
            return 0.0
        edad = (dt_util.utcnow() - self.actualizado).total_seconds()
        return max(0.0, CATALOGO_REFRESCO - edad)

    async def _cargar_disco(self) -> None:
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return
        try:
            self.lineas = {int(k): v for k, v in data["lineas"].items()}
            self.paradas = {int(k): v for k, v in data["paradas"].items()}
            self.fecha = data.get("fecha")
            self.actualizado = dt_util.parse_datetime(data.get("actualizado") or "")
        except (KeyError, ValueError, AttributeError):
            self.lineas, self.paradas = {}, {}

    async def _descargar(self) -> None:
        try:
            cat = await async_get_catalogo(async_get_clientsession(self.hass))
        except ItranviasError:
            self._fallos += 1
            espera = min(CATALOGO_ESPERA_ERROR * 2 ** (self._fallos - 1), CATALOGO_REFRESCO)
            self._proximo_intento = time.monotonic() + espera
            raise
        self._fallos = 0
        self.lineas, self.paradas, self.fecha = cat["lineas"], cat["paradas"], cat["fecha"]
        self.actualizado = dt_util.utcnow()
        self._proximo_intento = time.monotonic() + CATALOGO_REFRESCO
        await self._store.async_save(
            {
                "fecha": self.fecha,
                "actualizado": self.actualizado.isoformat(),
                "lineas": {str(k): v for k, v in self.lineas.items()},
                "paradas": {str(k): v for k, v in self.paradas.items()},
            }
        )

    # -- refresco en segundo plano ---------------------------------------
    def programar_refresco(self, urgente: bool = False) -> None:
        """Refresca si toca, sin bloquear la consulta de llegadas."""
        if self._en_curso or self._lock.locked():
            return
        ahora = time.monotonic()
        toca = ahora >= self._proximo_intento
        toca_urgente = urgente and ahora >= self._proximo_urgente
        if not (toca or toca_urgente):
            return
        if toca_urgente:
            self._proximo_urgente = ahora + CATALOGO_ESPERA_URGENTE
        self._en_curso = True
        self.hass.async_create_background_task(self._refrescar(), f"{DOMAIN}_catalogo")

    async def _refrescar(self) -> None:
        try:
            async with self._lock:
                await self._descargar()
        except ItranviasError as err:
            _LOGGER.warning("No se pudo refrescar el catálogo (se mantiene la caché): %s", err)
        finally:
            self._en_curso = False


def get_catalogo(hass: HomeAssistant) -> CatalogoManager:
    datos = hass.data.setdefault(DOMAIN, {})
    if "catalogo" not in datos:
        datos["catalogo"] = CatalogoManager(hass)
    return datos["catalogo"]
