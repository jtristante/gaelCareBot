# Changelog

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
