"""Configuración por la interfaz: número de parada, máximo de llegadas e intervalo."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import ItranviasError
from .catalogo import get_catalogo
from .const import (
    CONF_INTERVALO,
    CONF_MAX_LLEGADAS,
    CONF_PARADA,
    CONF_PAUSA_DESDE,
    CONF_PAUSA_HASTA,
    DEFAULT_INTERVALO,
    DEFAULT_MAX_LLEGADAS,
    DEFAULT_PAUSA_DESDE,
    DEFAULT_PAUSA_HASTA,
    DOMAIN,
    excede_limite,
    horas_activas,
    intervalo_minimo,
    MAX_INTERVALO,
    MAX_MAX_LLEGADAS,
    MIN_INTERVALO,
)


def _esquema_opciones(intervalo: int, maximo: int, desde: str, hasta: str) -> dict:
    return {
        vol.Required(CONF_MAX_LLEGADAS, default=maximo): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_MAX_LLEGADAS)
        ),
        vol.Required(CONF_INTERVALO, default=intervalo): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_INTERVALO, max=MAX_INTERVALO)
        ),
        vol.Required(CONF_PAUSA_DESDE, default=desde): selector.TimeSelector(),
        vol.Required(CONF_PAUSA_HASTA, default=hasta): selector.TimeSelector(),
    }


def _paradas_otras(hass, excluir: str | None = None) -> list[tuple[int, float]]:
    return [
        (
            e.options.get(CONF_INTERVALO, DEFAULT_INTERVALO),
            horas_activas(
                e.options.get(CONF_PAUSA_DESDE, DEFAULT_PAUSA_DESDE),
                e.options.get(CONF_PAUSA_HASTA, DEFAULT_PAUSA_HASTA),
            ),
        )
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != excluir
    ]


def _comprobar_limite(hass, datos: dict, excluir: str | None = None):
    """Devuelve (error, placeholders) si la suma de paradas supera el límite diario."""
    otras = _paradas_otras(hass, excluir)
    horas = horas_activas(datos[CONF_PAUSA_DESDE], datos[CONF_PAUSA_HASTA])
    minimo = intervalo_minimo(len(otras) + 1, horas)
    # Vale si el total cabe en el límite, o si este intervalo ya es el recomendado para el
    # número de paradas: así se pueden ir corrigiendo las paradas una a una sin quedarse
    # bloqueado por las que todavía tienen el intervalo antiguo.
    if excede_limite(otras + [(datos[CONF_INTERVALO], horas)]) and datos[CONF_INTERVALO] < minimo:
        return "intervalo_demasiado_bajo", {"minimo": str(minimo)}
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
            error_lim, placeholders = _comprobar_limite(self.hass, user_input)
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
                            CONF_PAUSA_DESDE: user_input[CONF_PAUSA_DESDE],
                            CONF_PAUSA_HASTA: user_input[CONF_PAUSA_HASTA],
                        },
                    )

        esquema = {
            vol.Required(CONF_PARADA): vol.All(vol.Coerce(int), vol.Range(min=1)),
            **_esquema_opciones(
                DEFAULT_INTERVALO,
                DEFAULT_MAX_LLEGADAS,
                DEFAULT_PAUSA_DESDE,
                DEFAULT_PAUSA_HASTA,
            ),
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
                self.hass, user_input, self.config_entry.entry_id
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
                    o.get(CONF_PAUSA_DESDE, DEFAULT_PAUSA_DESDE),
                    o.get(CONF_PAUSA_HASTA, DEFAULT_PAUSA_HASTA),
                )
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
