# GaelCareBot

Bot de Telegram para gestionar el stock de leche materna. Permite registrar extracciones, consumos y consultar el inventario actual.

## Requisitos

- Python 3.11+
- Docker y Docker Compose (opcional, para despliegue con contenedores)

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `BOT_TOKEN` | Sí | Token del bot de Telegram (se obtiene de @BotFather) |
| `AUTHORIZED_USER_IDS` | Sí | IDs de usuario de Telegram autorizados, separados por coma |
| `GROUP_CHAT_ID` | No | ID del grupo de Telegram para notificaciones (opcional) |
| `DB_PATH` | No | Ruta del archivo SQLite (por defecto: `data/milk.db`) |
| `TIMEZONE` | No | Zona horaria (por defecto: `Europe/Madrid`) |
| `CONVERSATION_TIMEOUT` | No | Tiempo de espera de conversación en segundos (por defecto: 300) |

## Configuración inicial

### 1. Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**.
2. Envía `/newbot` y sigue las instrucciones.
3. Guarda el token que te proporciona (es el `BOT_TOKEN`).

### 2. Obtener el ID del grupo (opcional)

1. Añade el bot al grupo como administrador.
2. Envía un mensaje en el grupo.
3. Visita `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`.
4. Busca `chat.id` en la respuesta JSON — ese es tu `GROUP_CHAT_ID`.

### 3. Obtener los IDs de usuario

1. Busca **@userinfobot** en Telegram.
2. Envía `/start` y luego reenvía cualquier mensaje.
3. El bot te devolverá tu ID numérico — ese es el `AUTHORIZED_USER_IDS`.

### 4. Configurar el archivo `.env`

Copia `.env.example` a `.env` y rellena los valores:

```bash
cp .env.example .env
```

Edita el archivo `.env` con tu editor favorito y completa al menos `BOT_TOKEN` y `AUTHORIZED_USER_IDS`.

## Despliegue con Docker (recomendado)

```bash
# Construir y levantar el contenedor
docker-compose up -d

# Ver logs en tiempo real
docker-compose logs -f

# Detener el contenedor
docker-compose down
```

Los datos de la base de datos SQLite se almacenan en `./data/` y persisten entre reinicios del contenedor.

## Despliegue sin Docker

```bash
# Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el bot
python -m src.bot
```

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Mensaje de bienvenida e instrucciones |
| `/agregar <cantidad>` | Registrar una extracción de leche (en ml) |
| `/consumir` | Registrar un consumo de leche (seleccionar de la lista) |
| `/stock` | Consultar el stock actual disponible |
| `/total` | Ver el total acumulado de extracciones y consumos |

## Estructura del proyecto

```
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── src/
│   ├── bot.py            # Punto de entrada principal
│   ├── config.py         # Configuración desde variables de entorno
│   ├── auth.py           # Autenticación de usuarios
│   ├── db.py             # Base de datos SQLite
│   ├── messages.py       # Mensajes y textos del bot
│   ├── group_notifier.py # Notificaciones a grupo
│   └── handlers/         # Manejadores de comandos
└── tests/
```
