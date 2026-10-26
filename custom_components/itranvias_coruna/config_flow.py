"""Configuración por la interfaz: número de parada, máximo de llegadas e intervalo."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .api import ItranviasError
from .catalogo import get_catalogo
from .const import (
    CONF_INTERVALO,
    CONF_MAX_LLEGADAS,
    CONF_PARADA,
    DEFAULT_INTERVALO,
    DEFAULT_MAX_LLEGADAS,
    DOMAIN,
    excede_limite,
    intervalo_minimo,
    MAX_INTERVALO,
    MAX_MAX_LLEGADAS,
    MIN_INTERVALO,
)


def _esquema_opciones(intervalo: int, maximo: int) -> dict:
    return {
        vol.Required(CONF_MAX_LLEGADAS, default=maximo): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_MAX_LLEGADAS)
        ),
        vol.Required(CONF_INTERVALO, default=intervalo): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_INTERVALO, max=MAX_INTERVALO)
        ),
    }


def _intervalos_otras(hass, excluir: str | None = None) -> list[int]:
    return [
        e.options.get(CONF_INTERVALO, DEFAULT_INTERVALO)
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != excluir
    ]


def _comprobar_limite(hass, intervalo: int, excluir: str | None = None):
    """Devuelve (error, placeholders) si la suma de paradas supera el límite diario."""
    otras = _intervalos_otras(hass, excluir)
    if excede_limite(otras + [intervalo]):
        return "intervalo_demasiado_bajo", {"minimo": str(intervalo_minimo(len(otras) + 1))}
    return None, {}


class ItranviasConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            parada = user_input[CONF_PARADA]
            await self.async_set_unique_id(str(parada))
            self._abort_if_unique_id_configured()
            catalogo = get_catalogo(self.hass)
            error_lim, placeholders = _comprobar_limite(
                self.hass, user_input[CONF_INTERVALO]
            )
            try:
                await catalogo.async_asegurar()
            except ItranviasError:
                errors["base"] = "cannot_connect"
            else:
                if error_lim:
                    errors[CONF_INTERVALO] = error_lim
                elif parada not in catalogo.paradas:
                    errors[CONF_PARADA] = "parada_desconocida"
                else:
                    return self.async_create_entry(
                        title=f"Parada {parada} · {catalogo.nombre_parada(parada)}",
                        data={CONF_PARADA: parada},
                        options={
                            CONF_MAX_LLEGADAS: user_input[CONF_MAX_LLEGADAS],
                            CONF_INTERVALO: user_input[CONF_INTERVALO],
                        },
                    )

        esquema = {
            vol.Required(CONF_PARADA): vol.All(vol.Coerce(int), vol.Range(min=1)),
            **_esquema_opciones(DEFAULT_INTERVALO, DEFAULT_MAX_LLEGADAS),
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(esquema),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return ItranviasOptionsFlow()


class ItranviasOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            error_lim, placeholders = _comprobar_limite(
                self.hass, user_input[CONF_INTERVALO], self.config_entry.entry_id
            )
            if error_lim:
                errors[CONF_INTERVALO] = error_lim
            else:
                return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                _esquema_opciones(
                    o.get(CONF_INTERVALO, DEFAULT_INTERVALO),
                    o.get(CONF_MAX_LLEGADAS, DEFAULT_MAX_LLEGADAS),
                )
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
