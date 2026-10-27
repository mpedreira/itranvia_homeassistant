# iTranvías A Coruña para Home Assistant

Muestra cuánto falta para que lleguen los autobuses a una parada de A Coruña, con los datos de iTranvías (Compañía de Tranvías de La Coruña). Solo necesitas el **número de parada**: se recogen todas las líneas y todos los vehículos que vienen.

## Aviso

Integración no oficial. Usa la API web de iTranvías, que **no tiene documentación oficial ni garantía de estabilidad** y puede cambiar o dejar de funcionar sin aviso. Lecturas públicas sin autenticación. El intervalo (por defecto 180 s) es un valor inicial configurable, no una frecuencia autorizada por el proveedor; no lo bajes sin necesidad.

## Instalación
**HACS:** menú ⋮ → *Repositorios personalizados* → URL de este repositorio, categoría *Integración* → instalar y reiniciar.
**Manual:** copia `custom_components/itranvias_coruna` en `/config/custom_components/` y reinicia.

## Configuración
Ajustes → Dispositivos y servicios → Añadir integración → *iTranvías A Coruña*:
- **Número de parada** (se comprueba contra el catálogo).
- **Máximo de llegadas** a mostrar en `llegadas` y `texto` (por defecto 4).
- **Intervalo de consulta** en segundos (por defecto 180, entre 90 y 600).
- **Pausa nocturna**: desde y hasta qué hora no se consulta (por defecto 00:30–05:30).

Se puede repetir para varias paradas. Las dos últimas opciones se cambian después en *Configurar*.

## Icono
La integración incluye un icono propio (un tranvía genérico) en `brand/`, que Home Assistant usa en recientes versiones al mostrar integraciones personalizadas. No es el logotipo de iTranvías: es un dibujo original para no usar marcas ajenas.

## Entidades (una parada = un dispositivo)
| Entidad | Estado | Atributos |
|---|---|---|
| `Próximo bus` | `<1`, `3`... (minutos) o `Sin buses` | `llegadas` (hasta el máximo, ordenadas), `texto` (una línea por llegada, p. ej. `12A  <1 min`), `parada`, `parada_nombre`, `linea`, `actualizado`, `catalogo_fecha` |
| `Buses en camino` | nº de vehículos con tiempo | |
| `Línea 12A`, `Línea 20`... (una por línea de la parada) | tiempo del siguiente vehículo o `Sin buses` | `buses` (todos los de esa línea), `origen`, `destino`, `color` (RGB hex sin `#`) |
| `Última actualización` (diagnóstico) | marca de tiempo de la última consulta correcta | `consulta_correcta` |

Cada llegada (en `llegadas` y `buses`) trae: `linea`, `color`, `tiempo` (texto), `minutos` (número o `null`), `menor_que_1`, `vehiculo`, `distancia_m`, `estado`, `ultima_parada` (nombre) y `ultima_parada_id`.

## Comportamiento
- **Nombres:** siempre el nombre comercial (`12A`, `20`, `BUH`), nunca el ID interno de línea ni el número de vehículo. Salen del catálogo de iTranvías, que se descarga una vez, se guarda en disco y se refresca cada 24 h (no se descarga en cada consulta). Si llega una línea desconocida se permite un refresco como mucho cada hora; mientras tanto se muestra `?`.
- **Tiempos:** `<1` se conserva como `<1` (no se convierte en 0 exacto). Orden: primero `<1`, luego minutos ascendentes y al final los desconocidos (`?`).
- **Sin buses ≠ fallo:** sin vehículos activos las entidades dicen `Sin buses`; si falla la conexión pasan a *no disponible* (no se muestran datos viejos como actuales) y `Última actualización` indica cuándo fue la última consulta buena.
- **Fallos:** timeout, HTTP, JSON inválido, nulos y listas vacías están controlados. Tras un fallo las consultas se espacian (retroceso exponencial hasta 15 min); ante 403/429/503 se espera al menos 5 min. Si el catálogo falla se mantiene la caché.
- Las entidades de línea se crean desde el principio para todas las líneas que pasan por la parada (según el catálogo), aunque no tengan vehículos en ese momento.

## Limitaciones
- `distancia_m`: la API no documenta las unidades; se asumen metros.
- `estado` (0/1): se observa pero no se interpreta, se publica tal cual.
- Si la API cambia, el parser puede dejar de funcionar.

## Desarrollo
Pruebas del parser (sin Home Assistant): `python -m unittest discover tests`. Los datos de prueba son sintéticos, basados en la descripción del contrato. La integración completa no tiene aún pruebas automáticas dentro de Home Assistant.

## Colaborar
Lee [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia
[GNU LGPL v3](LICENSE). No es un producto oficial de iTranvías ni de la Compañía de Tranvías de La Coruña.

## Límites de consultas

El proveedor responde `429 Too Many Requests` si se supera: 1 consulta por segundo, 4 por minuto, 199 por hora y 1999 por día. Cada parada hace una consulta por intervalo, así que el que manda es el diario.

Intervalo mínimo recomendado por parada (con el margen del 80 % del límite diario):

| Paradas | Sin pausa nocturna | Con pausa 00:30–05:30 (19 h activas) |
|---|---|---|
| 1 | 55 s | 43 s |
| 2 | 109 s | 86 s |
| 3 | 163 s | 129 s |

**Pausa nocturna.** Entre las horas "No consultar desde" y "No consultar hasta" (por defecto 00:30 y 05:30, hora de Home Assistant) la integración no consulta al proveedor y los sensores marcan "Sin buses". Si las dos horas son iguales, no hay pausa. Admite pausas que cruzan medianoche (por ejemplo 23:00–06:00).

La integración comprueba el límite al configurar (rechaza intervalos que, sumando todas las paradas y descontando la pausa, pasen del 80 % del límite diario), escalona las paradas al arrancar y, si el proveedor bloquea, crea un aviso en Reparaciones con el intervalo recomendado.
