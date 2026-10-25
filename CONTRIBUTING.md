# Cómo colaborar

Gracias por querer mejorar la integración. Cualquier ayuda es bienvenida: avisar de un fallo, corregir un texto, probar con otras paradas o mandar código.

## Antes de empezar

Esta integración usa la API web de iTranvías, que **no tiene documentación oficial ni garantía de estabilidad**. Por eso:

- No añadas peticiones a operaciones de la API que no estén ya comprobadas (hoy solo `func=0` para llegadas y `func=7` para el catálogo). Si propones una nueva, explica cómo la has comprobado y adjunta una respuesta de ejemplo.
- No bajes los intervalos de consulta por defecto ni quites los controles de fallos y de espera: la idea es ser respetuosos con el servidor.
- No incluyas el logotipo ni otros materiales de marca de iTranvías o de la Compañía de Tranvías.

## Avisar de un fallo

Abre una *issue* con:

1. Versión de Home Assistant y de la integración (`manifest.json`).
2. Número de parada y qué esperabas ver frente a lo que ves.
3. Las líneas del log de Home Assistant que mencionen `itranvias_coruna`.
4. Si puedes, la respuesta de la API para esa parada
   (`https://itranvias.com/queryitr_v3.php?&func=0&dato=<parada>`). Quita cualquier dato que no quieras compartir.

## Proponer cambios

1. Haz un *fork* y crea una rama a partir de `main` (`fix/...` o `feature/...`).
2. Mantén el cambio pequeño y centrado en una cosa.
3. Ejecuta las pruebas del parser, que no necesitan Home Assistant:
   ```
   python -m unittest discover tests
   ```
4. Si cambias el comportamiento del parser, añade o ajusta una prueba. Los datos de prueba son sintéticos, basados en la descripción del contrato; no pegues respuestas reales enteras.
5. Si cambias textos de la interfaz, actualiza `strings.json` y las tres traducciones (`es`, `gl`, `en`).
6. Si cambias el nombre o el significado de una entidad o atributo, actualiza la tabla del `README.md`.
7. Abre una *pull request* explicando qué cambia y por qué, y qué has probado (y qué no).

## Estilo

- Python con tipos (`from __future__ import annotations`) y `async` para todo lo que haga red.
- Sin dependencias externas nuevas salvo que haya una razón clara.
- Nombres de línea siempre los comerciales (`12A`, `20`), nunca los IDs internos ni el número de vehículo.
- Los comentarios y el README, en español.

## Probar en tu Home Assistant

Copia `custom_components/itranvias_coruna` a `/config/custom_components/`, reinicia Home Assistant y añade la integración desde Ajustes → Dispositivos y servicios. La integración completa aún no tiene pruebas automáticas dentro de Home Assistant: toda ayuda para añadirlas es muy bienvenida.

## Licencia

Al enviar una contribución aceptas que se publique bajo la licencia del proyecto, **LGPL-3.0** (ver `LICENSE`).
