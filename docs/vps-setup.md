# VPS Setup Guide — GaelCareBot

Guía para configurar el self-hosted runner de GitHub Actions en el VPS y desplegar GaelCareBot.

## Prerrequisitos

- VPS Linux (Ubuntu/Debian) con acceso por Tailscale
- Docker y Docker Compose instalados
- Git instalado
- Acceso root o sudo
- Repositorio `jtristante/gaelcarebot` en GitHub

## Estructura de directorios

Crear la siguiente estructura en el VPS:

```
/opt/gaelcarebot/
├── docker-compose.yml        # (desde el repo)
├── docker-compose.prod.yml   # (desde el repo)
├── .env                      # (crear manualmente, ver abajo)
├── data/                     # (se crea automáticamente)
│   └── gael_care_bot.db      # Base de datos SQLite
└── actions-runner/           # Runner de GitHub Actions
    └── ...                   # (se instala en paso 2)
```

```bash
sudo mkdir -p /opt/gaelcarebot/data
sudo chown -R $USER:$USER /opt/gaelcarebot
```

## Configurar .env

```bash
cd /opt/gaelcarebot
cp .env.example .env
nano .env
```

Editar con los valores reales:

| Variable | Valor | Ejemplo (sustituir con valores reales) |
|---|---|---|
| `BOT_TOKEN` | Token de @BotFather | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `AUTHORIZED_USER_IDS` | Tu ID de Telegram | `987654321` |
| `GROUP_CHAT_ID` | ID del grupo (opcional) | `-1009876543210` |
| `DB_PATH` | Ruta BD (opcional) | `/data/gael_care_bot.db` |
| `TIMEZONE` | Zona horaria | `Europe/Madrid` |

## Instalar self-hosted runner

1. Ir al directorio:

```bash
mkdir -p /opt/gaelcarebot/actions-runner
cd /opt/gaelcarebot/actions-runner
```

2. Obtener el token de registro:

   - Ir a GitHub → Settings → Actions → Runners → New self-hosted runner
   - O ir a: `https://github.com/jtristante/gaelcarebot/settings/actions/runners/new`
   - Copiar el token de registro (no el de descarga)

3. Descargar y configurar:

```bash
# Reemplazar VERSION y TOKEN con los valores de GitHub
curl -o actions-runner-linux-x64-VERSION.tar.gz -L https://github.com/actions/runner/releases/download/vVERSION/actions-runner-linux-x64-VERSION.tar.gz
tar xzf actions-runner-linux-x64-VERSION.tar.gz

# Registrar el runner
./config.sh --url https://github.com/jtristante/gaelcarebot --token TOKEN --name gaelcarebot-runner --labels self-hosted --work /opt/gaelcarebot
```

4. Instalar como servicio systemd:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

5. Verificar que el runner está online:

```bash
sudo ./svc.sh status
```

Debes ver el runner como "online" en GitHub → Settings → Actions → Runners.

## Clonar config inicial

```bash
cd /opt/gaelcarebot
git clone https://github.com/jtristante/gaelcarebot.git temp
mv temp/* temp/.* . 2>/dev/null; rm -rf temp
```

O simplemente copia `docker-compose.yml` y `docker-compose.prod.yml` del repo.

## Verificación

```bash
# Verificar que el runner está activo
sudo systemctl status actions.runner.jtristante-gaelcarebot.gaelcarebot-runner.service

# Verificar que Docker funciona
docker ps

# Verificar que compose funciona
docker compose version

# Test de deploy manual
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose ps

# Verificar healthcheck
sleep 20 && docker compose ps --status healthy
```

## Pipeline CI/CD (automático)

Una vez configurado:

1. Cada push a `master` dispara **CI** (`.github/workflows/ci.yml`):
   - Ejecuta `pytest` en GitHub Actions (ubuntu-latest)
   - Si pasa: build + push a `ghcr.io/jtristante/gaelcarebot:latest`
2. CI exitoso dispara **Deploy** (`.github/workflows/deploy.yml`):
   - El runner del VPS recibe el evento
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans`
   - Espera healthcheck (hasta 120s)
   - Limpia imágenes viejas (`docker image prune -f`)

Puedes ver el estado en: `https://github.com/jtristante/gaelcarebot/actions`

## Troubleshooting

### Runner offline
```bash
cd /opt/gaelcarebot/actions-runner
sudo ./svc.sh status
# Si no corre: sudo ./svc.sh start
# Si sigue fallando: sudo ./svc.sh stop && sudo ./svc.sh uninstall
# Re-registrar: ./config.sh remove --token NUEVO_TOKEN
# Re-instalar: sudo ./svc.sh install && sudo ./svc.sh start
```

### Token expirado
El token de registro expira después de 1 hora. Si expiró, genera uno nuevo en GitHub → Settings → Actions → Runners y usa `./config.sh` con el nuevo token.

### Permisos de Docker
```bash
# Si el runner no puede ejecutar docker:
sudo usermod -aG docker $USER
# Luego reiniciar sesión o: newgrp docker
```

### Error de healthcheck en deploy
- Revisar logs: `docker compose logs gaelcarebot`
- Verificar que `.env` tiene `BOT_TOKEN` y `AUTHORIZED_USER_IDS` correctos
- Hacer deploy manual para debug: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### Nota sobre tokens
El token de registro del runner expira cada hora si no se usa `--ephemeral`. El servicio systemd maneja la renovación automáticamente. Si el runner se desconecta, reinicia el servicio.
