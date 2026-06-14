"""Messages module for GaelCareBot.

All user-facing text strings in Spanish. Constants use .format() for
parameter substitution — callers must supply the named placeholders.
"""

# ── Welcome & Help ──────────────────────────────────────────────────────────

# Welcome message shown on /start.
WELCOME_MSG = (
    "👋 ¡Bienvenido a GaelCareBot! 🤱\n\n"
    "Gestiona el stock de leche materna de tu bebé.\n\n"
    "Usa /help para ver los comandos disponibles."
)

# Help message listing all commands.
HELP_MSG = (
    "📋 <b>Comandos disponibles:</b>\n\n"
    "/start — Mensaje de bienvenida e instrucciones\n"
    "/help — Mostrar esta ayuda\n"
    "/agregar <code>[cantidad]</code> <code>[notas]</code> — Registrar leche extraída. Sin argumentos abre menú interactivo\n"
    "/consumir — Registrar leche consumida (seleccionar de la lista)\n"
    "/stock — Ver historial completo\n"
    "/total — Ver stock total disponible\n"
    "/editar — Editar una entrada existente\n"

)

# ── Error messages ──────────────────────────────────────────────────────────

# User is not in the authorized list.
ERROR_UNAUTHORIZED = "⛔ No tienes permiso para usar este bot."

# Provided amount is not a positive integer.
ERROR_INVALID_AMOUNT = "❌ Cantidad inválida. Debe ser un número entero positivo (ml)."

# Date does not match DD/MM/YYYY format.
ERROR_INVALID_DATE = "❌ Fecha inválida. Usa el formato DD/MM/YYYY (ej: 19/05/2026)."

# Not enough stock to cover the requested consumption.
ERROR_INSUFFICIENT_STOCK = "❌ Stock insuficiente. Disponible: {stock} ml."

# The requested entry could not be found in the database.
ERROR_ENTRY_NOT_FOUND = "❌ Entrada no encontrada."

# Generic unhandled error.
ERROR_GENERIC = "❌ Ha ocurrido un error. Intenta de nuevo."

# No entries exist (for listing / stock display).
ERROR_NO_ENTRIES = "📭 No hay entradas registradas."

# Date is in the future (not allowed).
ERROR_FUTURE_DATE = "❌ No se permiten fechas futuras."

# ── Success messages ────────────────────────────────────────────────────────

# Confirmation after adding milk expression.
MSG_ADDED = "✅ {cantidad} ml de leche añadidos el {fecha}."

# Confirmation after registering consumption.
MSG_CONSUMED = "🍼 {cantidad} ml de leche consumidos el {fecha}."

# Current total stock (positive balance).
MSG_STOCK_TOTAL = "📊 Stock total: {cantidad} ml"

# Current total stock when balance is zero.
MSG_STOCK_TOTAL_ZERO = "📊 Stock total: 0 ml. ¡Es hora de extraer!"

# Confirmation after deleting an entry.
MSG_DELETED = "🗑️ Entrada eliminada correctamente."

# Confirmation after reversing an entry (ENTRADA → SALIDA).
MSG_REVERSED = "🔄 Entrada #{entry_id} cambiada a SALIDA."

# Confirmation after updating an entry.
MSG_UPDATED = "✏️ Entrada actualizada correctamente."

# ── Interactive flow messages ───────────────────────────────────────────────

# Confirmation prompt before deleting an entry.
MSG_CONFIRM_DELETE = "¿Estás seguro de eliminar esta entrada?\n\n{entry_info}"

# Prompt to select an entry from the list.
MSG_SELECT_ENTRY = "Selecciona una entrada:"

# User cancelled the current operation.
MSG_CANCELLED = "Operación cancelada."

# Conversation timeout reached.
MSG_TIMEOUT = "⏰ Tiempo de espera agotado. Operación cancelada."

# Prompt to select a field to edit.
MSG_SELECT_FIELD = "Selecciona el campo a editar:"

# Prompt to enter a new value for a specific field.
MSG_ENTER_NEW_VALUE = "Introduce el nuevo valor para '{campo}':"

# Prompt for amount when /agregar is used without arguments (interactive mode).
MSG_PROMPT_AMOUNT = "¿Cuántos ml quieres añadir?"

# Confirmation prompt before applying edits.
MSG_CONFIRM_EDIT = "¿Confirmar cambios?\n\n{entry_info}"

# ── Summary messages ────────────────────────────────────────────────────────

# Header for day summary, with date.
SUMMARY_HEADER = "📋 Resumen del día {fecha}:"

# Line item for milk added (expression) in the summary.
SUMMARY_ENTRADAS = "  +{cantidad} ml (extracción) - {responsable}"

# Line item for milk consumed in the summary.
SUMMARY_SALIDAS = "  -{cantidad} ml (consumo) - {responsable}"

# Balance line at the end of the summary.
SUMMARY_BALANCE = "  Balance: {balance} ml"

# Shown when there is no activity for the requested day.
SUMMARY_NO_ACTIVITY = "Sin actividad registrada."

# ── Table formatting ────────────────────────────────────────────────────────

# Header row for the stock history table.
TABLE_HEADER = (
    "<b>🗓️ Historial de stock</b>\n\n"
    "<pre>ID  Fecha        Tipo     Cantidad  Responsable  Notas</pre>"
)

# ── Inline button labels ────────────────────────────────────────────────────

# Cancel button for interactive flows.
BTN_CANCEL = "❌ Cancelar"

# Confirm / Yes button.
BTN_CONFIRM = "✅ Sí"

# Deny / No button.
BTN_DENY = "No"

# Edit button for the "cantidad" field.
BTN_EDIT_CANTIDAD = "Cantidad"

# Edit button for the "fecha" field.
BTN_EDIT_FECHA = "Fecha"

# Edit button for the "notas" field.
BTN_EDIT_NOTAS = "Notas"

# Edit button for the "tipo" field.
BTN_EDIT_TIPO = "Tipo"
