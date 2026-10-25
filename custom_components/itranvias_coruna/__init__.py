"""Integración iTranvías A Coruña: llegadas de autobús por parada."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import ItranviasError
from .catalogo import get_catalogo
from .const import PLATFORMS
from .coordinator import ItranviasCoordinator

type ItranviasConfigEntry = ConfigEntry[ItranviasCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ItranviasConfigEntry) -> bool:
    catalogo = get_catalogo(hass)
    try:
        await catalogo.async_asegurar()
    except ItranviasError as err:
        # Sin catálogo no se pueden mostrar nombres de línea: se reintenta luego.
        raise ConfigEntryNotReady(f"Catálogo de iTranvías no disponible: {err}") from err

    coordinator = ItranviasCoordinator(hass, entry, catalogo)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_recargar))
    return True


async def _recargar(hass: HomeAssistant, entry: ItranviasConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ItranviasConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
