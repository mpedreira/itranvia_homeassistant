"""Sensores: próximo bus, buses en camino, una entidad por línea y última actualización."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ItranviasConfigEntry
from .api import clave_orden, texto_tiempo
from .const import DOMAIN
from .coordinator import ItranviasCoordinator

SIN_BUSES = "Sin buses"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ItranviasConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    catalogo = coordinator.catalogo
    # Una entidad por cada línea que pasa por la parada (enlaces del catálogo),
    # aunque ahora mismo no tenga vehículos activos.
    conocidas: set[int] = set(catalogo.enlaces(coordinator.parada))
    async_add_entities(
        [
            ProximoSensor(coordinator),
            ConteoSensor(coordinator),
            UltimaActualizacionSensor(coordinator),
            *(LineaSensor(coordinator, l) for l in sorted(conocidas)),
        ]
    )

    @callback
    def _lineas_nuevas() -> None:
        nuevas = [l for l in coordinator.data if l not in conocidas]
        if nuevas:
            conocidas.update(nuevas)
            async_add_entities(LineaSensor(coordinator, l) for l in nuevas)

    entry.async_on_unload(coordinator.async_add_listener(_lineas_nuevas))


class _Base(CoordinatorEntity[ItranviasCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ItranviasCoordinator) -> None:
        super().__init__(coordinator)
        nombre = coordinator.catalogo.nombre_parada(coordinator.parada)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.parada))},
            name=f"Parada {coordinator.parada}" + (f" · {nombre}" if nombre else ""),
            manufacturer="Compañía de Tranvías de La Coruña",
            model="Parada de autobús",
        )

    def _detalle(self, id_linea: int, bus: dict[str, Any]) -> dict[str, Any]:
        cat = self.coordinator.catalogo
        info = cat.info_linea(id_linea)
        return {
            "linea": cat.nombre_linea(id_linea),
            "color": info.get("color"),
            "tiempo": texto_tiempo(bus),  # "<1", "3" o "?"
            "minutos": bus["minutos"],  # None si es "<1" o desconocido
            "menor_que_1": bus["menor_que_1"],
            "vehiculo": bus["vehiculo"],
            "distancia_m": bus["distancia"],  # unidades no documentadas, presumiblemente metros
            "estado": bus["estado"],  # sin interpretar
            "ultima_parada_id": bus["ult_parada"],
            "ultima_parada": cat.nombre_parada(bus["ult_parada"]),
            "id_linea": id_linea,
        }

    def _todos(self) -> list[dict[str, Any]]:
        """Todos los vehículos de la parada, ordenados: "<1", minutos, desconocidos."""
        pares = [
            (id_linea, bus)
            for id_linea, buses in self.coordinator.data.items()
            for bus in buses
        ]
        pares.sort(key=lambda p: clave_orden(p[1]))
        return [self._detalle(i, b) for i, b in pares]

    def _comunes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            "actualizado": c.ultimo_ok.isoformat() if c.ultimo_ok else None,
            "catalogo_fecha": c.catalogo.fecha,
        }


class ProximoSensor(_Base):
    """Primer vehículo que llegue, de cualquier línea. Estado: "<1", "3"... o "Sin buses"."""

    _attr_translation_key = "proximo"
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: ItranviasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.parada}_proximo"

    @property
    def native_value(self) -> str:
        todos = self._todos()
        return todos[0]["tiempo"] if todos else SIN_BUSES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        todos = self._todos()
        limitados = todos[: self.coordinator.max_llegadas]
        texto = "\n".join(f"{d['linea']}  {d['tiempo']} min" for d in limitados)
        return {
            "unidad": "min",
            "parada": self.coordinator.parada,
            "parada_nombre": self.coordinator.catalogo.nombre_parada(self.coordinator.parada),
            "linea": todos[0]["linea"] if todos else None,
            "llegadas": limitados,
            "texto": texto or SIN_BUSES,
            **self._comunes(),
        }


class ConteoSensor(_Base):
    """Número de vehículos de la parada con tiempo de llegada."""

    _attr_translation_key = "conteo"
    _attr_icon = "mdi:bus-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ItranviasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.parada}_conteo"

    @property
    def native_value(self) -> int:
        return sum(len(b) for b in self.coordinator.data.values())


class LineaSensor(_Base):
    """Siguiente vehículo de una línea; todos los de esa línea en atributos."""

    _attr_icon = "mdi:bus"

    def __init__(self, coordinator: ItranviasCoordinator, id_linea: int) -> None:
        super().__init__(coordinator)
        self._id = id_linea
        info = coordinator.catalogo.info_linea(id_linea)
        self._attr_unique_id = f"{coordinator.parada}_{id_linea}"
        self._attr_name = f"Línea {coordinator.catalogo.nombre_linea(id_linea)}"
        self._origen = info.get("origen")
        self._destino = info.get("destino")

    @property
    def native_value(self) -> str:
        buses = self.coordinator.data.get(self._id)
        return texto_tiempo(buses[0]) if buses else SIN_BUSES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        buses = self.coordinator.data.get(self._id) or []
        info = self.coordinator.catalogo.info_linea(self._id)
        return {
            "unidad": "min",
            "linea": self.coordinator.catalogo.nombre_linea(self._id),
            "color": info.get("color"),
            "origen": self._origen,
            "destino": self._destino,
            "buses": [self._detalle(self._id, b) for b in buses],
            **self._comunes(),
        }


class UltimaActualizacionSensor(_Base):
    """Cuándo se consultó la parada con éxito por última vez.

    Se mantiene disponible aunque la conexión falle: así se distingue "sin buses"
    (los demás sensores dicen "Sin buses") de "fallo de conexión" (no disponibles).
    """

    _attr_translation_key = "ultima_actualizacion"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ItranviasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.parada}_ultima_actualizacion"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.ultimo_ok

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"consulta_correcta": self.coordinator.last_update_success}
