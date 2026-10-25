"""Coordinador de actualización de llegadas de una parada."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ItranviasError, async_get_llegadas
from .catalogo import CatalogoManager
from .const import (
    CONF_INTERVALO,
    CONF_MAX_LLEGADAS,
    CONF_PARADA,
    DEFAULT_INTERVALO,
    DEFAULT_MAX_LLEGADAS,
    DOMAIN,
    ESPERA_MAXIMA,
    ESPERA_MINIMA_BLOQUEO,
)

_LOGGER = logging.getLogger(__name__)


class ItranviasCoordinator(DataUpdateCoordinator[dict[int, list[dict[str, Any]]]]):
    """Consulta periódica de una parada.

    Si la consulta falla, los sensores pasan a no disponibles (no se muestran datos
    antiguos como actuales) y las consultas se espacian con retroceso exponencial.
    """

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, catalogo: CatalogoManager
    ) -> None:
        self.parada: int = entry.data[CONF_PARADA]
        self.catalogo = catalogo
        self.max_llegadas: int = entry.options.get(CONF_MAX_LLEGADAS, DEFAULT_MAX_LLEGADAS)
        self._intervalo_base: int = entry.options.get(CONF_INTERVALO, DEFAULT_INTERVALO)
        self._fallos = 0
        self.ultimo_ok: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.parada}",
            update_interval=timedelta(seconds=self._intervalo_base),
        )

    async def _async_update_data(self) -> dict[int, list[dict[str, Any]]]:
        try:
            llegadas = await async_get_llegadas(
                async_get_clientsession(self.hass), self.parada
            )
        except ItranviasError as err:
            self._fallos += 1
            espera = self._intervalo_base * 2 ** min(self._fallos, 5)
            if err.bloqueado:
                espera = max(espera, ESPERA_MINIMA_BLOQUEO)
            self.update_interval = timedelta(seconds=min(espera, ESPERA_MAXIMA))
            raise UpdateFailed(str(err)) from err

        self._fallos = 0
        self.update_interval = timedelta(seconds=self._intervalo_base)
        self.ultimo_ok = dt_util.utcnow()
        desconocidas = any(not self.catalogo.tiene_linea(l) for l in llegadas)
        self.catalogo.programar_refresco(urgente=desconocidas)
        return llegadas
