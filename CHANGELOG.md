# Changelog

## [2.0.0] - 2026-07-03

### Añadido

- **Stock**: fila de totales en la tabla de stock (`/stock`) que muestra la suma de todas las extracciones
- **Notificaciones**: persistencia de mensajes de resumen diario en base de datos (`daily_summary_messages` table)
- **Notificaciones**: edición de mensajes de resumen existentes en lugar de enviar duplicados (con fallback a nuevo mensaje si falla)
- **Notificaciones**: formato cronológico (orden ASC) con timestamps HH:MM en los resúmenes diarios
- **Tests**: cobertura de tests para la fila de totales en stock y la nueva estrategia de notificaciones

### Cambiado

- **Notificaciones**: estrategia de envío cambiada a "eliminar y reenviar" para garantizar notificaciones push en el grupo
- **Notificaciones**: firma de `send_daily_summary()` cambiada de `(bot, db)` a `(context, db)` para acceso completo al contexto
- **Handlers**: actualizados los puntos de llamada a `send_daily_summary` en `/agregar` y `/consumir` para pasar `context` en lugar de `context.bot`

### Corregido

- **Workflow**: manejo de entradas stash vacías en el flujo de release
- **Notificaciones**: formato de resumen revertido al clásico (sin timestamps) para mejor legibilidad
- **Tests**: corregido flakiness en tests de resumen diario causado por dependencias de zona horaria
- **CI**: merge del workflow de deploy en el CI con loop de reintentos y sistema de rollback para v2.0.0
- **CI**: cambio de `buildx imagetools` a `docker manifest inspect` para verificar imágenes
- **Release**: uso de Personal Access Token (PAT) para git push y activar workflows de CI

### Eliminado

- **Comandos**: eliminado el comando `/help` redundante (la funcionalidad se mantiene en `/start`)

[2.0.0]: https://github.com/jtristante/gaelcarebot/releases/tag/v2.0.0

## [1.0.0] - 2026-07-03

### Añadido

- **Bot core**: implementación completa del bot de Telegram con `python-telegram-bot` v20+
- **Comandos**:
  - `/agregar` — registro de extracciones con modo inline (cantidad directa) e interactivo (ConversationHandler)
  - `/consumir` — registro de consumo con doble modo: FIFO (con argumentos) y reversión (sin argumentos)
  - `/stock` — historial completo de extracciones con tabla formateada
  - `/total` — stock total disponible
  - `/editar` — edición de entradas existentes (cantidad, fecha, notas, tipo)
  - `/help` — mensaje de ayuda
  - `/start` — mensaje de bienvenida
- **Base de datos**: SQLite con WAL mode, esquema `milk_entries` con soporte de soft-delete (`consumed_at`), `consume_fifo()` para consumo FIFO, resúmenes por rango de fechas, y migraciones automáticas
- **Autenticación**: decorador `@authorized_only` con lista de IDs autorizados desde variable de entorno
- **Notificaciones**: resumen diario automático al grupo de Telegram tras cada operación de stock
- **Interfaz de usuario**: todos los textos en español, mensajes formateados con HTML
- **Manejo de errores**: handler global de excepciones que loguea errores y notifica al usuario
- **Docker**: Dockerfile multi-etapa con HEALTHCHECK, docker-compose para desarrollo, docker-compose.prod.yml para producción
- **sqlite-web**: servicio de navegador web para consultar la base de datos (acceso vía Tailscale)
- **CI/CD**: GitHub Actions para test → build (ARM64) → push a GHCR, y deploy a VPS con self-hosted runner
- **Tests**: suite completa con pytest (`asyncio_mode=auto`), tests de migraciones e integración
- **Scripts**: `scripts/bump_version.py` para gestionar versiones SNAPSHOT → release
- **Paquete Python**: estructura instalable vía `pip install .` con `pyproject.toml` (PEP 621)
- **Documentación**: `README.md` con comandos, `docs/vps-setup.md` (guía de VPS self-hosted runner), `docs/RELEASE.md` (guía de release workflow)

### Cambiado

### Corregido

### Rendimiento

### Eliminado

[1.0.0]: https://github.com/jtristante/gaelcarebot/releases/tag/v1.0.0
