# Añadir sqlite-web al docker-compose

## TL;DR

> **Quick Summary**: Añadir sqlite-web como servicio complementario en docker-compose.yml para acceder a la base de datos SQLite del GaelCareBot vía navegador, protegido con contraseña y accesible solo a través de la red privada Tailscale.
>
> **Deliverables**:
> - Servicio `sqlite-web` en `docker-compose.yml` (imagen `coleifer/sqlite-web`, puerto 8080, auth por contraseña)
> - Nuevas variables en `.env.example`: `SQLITE_WEB_PASSWORD`, `SQLITE_WEB_PORT`
> - Documentación de acceso en `README.md`
>
> **Estimated Effort**: Quick
> **Parallel Execution**: YES - 1 wave (3 parallel tasks)
> **Critical Path**: Ninguna (todas las tareas son independientes)

---

## Context

### Original Request
El usuario quiere acceder a la base de datos SQLite (`data/milk.db`) del GaelCareBot desde un navegador web, de forma remota pero segura. Ya usa Tailscale para conectar sus dispositivos a la VPS. Preguntó específicamente por sqlite-web como opción ligera.

### Interview Summary
**Key Discussions**:
- La DB persiste en la VPS vía bind mount `./data:/data` en docker-compose
- Tailscale proporciona conectividad directa sin necesidad de exponer puertos públicamente
- sqlite-web elegido sobre Datasette por ser más ligero (3 deps, ~25-40 MB RAM) y tener CRUD nativo
- Acceso planeado: `http://<tailscale-ip-vps>:8080` con contraseña
- Confirmado: `SQLITE_WEB_PASSWORD` es soportado oficialmente (lee de env var en vez de prompt interactivo)

**Research Findings**:
- Imagen Docker: `coleifer/sqlite-web` (Docker Hub), última versión 0.7.2 (marzo 2026)
- Dependencias mínimas: flask, peewee, pygments
- WAL mode compatible (GaelCareBot usa WAL)
- `-P` flag + `SQLITE_WEB_PASSWORD` env var = auth no-interactiva en Docker
- La imagen corre como root por defecto → necesita `user: "1000:1000"` para coincidir con `appuser` del GaelCareBot

### Metis Review
**Identified Gaps** (addressed):
- Puerto hardcodeado → `SQLITE_WEB_PORT` configurable (default 8080)
- Permisos entre contenedores → `user: "1000:1000"` para igualar UID
- Rotación de logs → `logging:` con max-size/max-file
- Health check → healthcheck HTTP al servicio
- Startup order → `depends_on` + nota en README
- Contraseña obligatoria → validación en documentación

---

## Work Objectives

### Core Objective
Añadir un servicio sqlite-web al docker-compose existente que permita navegar y editar la base de datos `milk.db` vía interfaz web, accesible exclusivamente a través de Tailscale con protección por contraseña.

### Concrete Deliverables
- `docker-compose.yml` modificado con nuevo servicio `sqlite-web`
- `.env.example` actualizado con `SQLITE_WEB_PASSWORD` y `SQLITE_WEB_PORT`
- `README.md` actualizado con sección de acceso vía sqlite-web

### Definition of Done
- [ ] `docker compose up -d` arranca ambos servicios sin errores
- [ ] `docker compose ps` muestra `sqlite-web` como `running`
- [ ] `curl http://vps-tailscale-ip:8080/` devuelve HTML de sqlite-web
- [ ] `curl http://vps-tailscale-ip:8080/` sin credenciales → redirige a login
- [ ] `curl -u :PASSWORD http://vps-tailscale-ip:8080/` con credenciales → acceso exitoso
- [ ] GaelCareBot sigue funcionando (consulta DB concurrente)

### Must Have
- Contraseña obligatoria (servicio no arranca sin `SQLITE_WEB_PASSWORD`)
- Escucha en `0.0.0.0` (necesario para Tailscale)
- Mismo volumen `./data:/data` que gaelcarebot
- Misma política de reinicio (`unless-stopped`)
- Log rotation configurado

### Must NOT Have (Guardrails)
- NO exponer puerto 8080 al host público (solo accesible vía Tailscale)
- NO modificar el servicio `gaelcarebot` existente
- NO añadir nginx, Traefik, ni ningún reverse proxy
- NO añadir HTTPS/SSL (Tailscale proporciona cifrado)
- NO modificar handlers, `db.py`, ni ningún código Python de GaelCareBot
- NO incluir valores reales de contraseña en documentación — usar placeholders obvios

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest para código Python), pero no aplica a cambios de docker-compose
- **Automated tests**: None (solo se modifican archivos YAML/Markdown, sin lógica nueva)
- **Framework**: N/A

### QA Policy
Verificación 100% vía comandos `docker compose` + `curl`. Sin tests unitarios necesarios.
Cada tarea incluye Agent-Executed QA Scenarios con pasos concretos.

- **CLI/Docker**: Usar Bash — `docker compose up`, `docker compose ps`, `docker compose logs`
- **HTTP/API**: Usar Bash (curl) — verificar endpoints, autenticación, respuestas

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - 3 parallel tasks, ninguna dependencia):
├── Task 1: Añadir servicio sqlite-web a docker-compose.yml [quick]
├── Task 2: Actualizar .env.example con nuevas variables [quick]
└── Task 3: Documentar acceso sqlite-web en README.md [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews, luego aprobación del usuario):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: Ninguna (todas las tareas son independientes)
Parallel Speedup: ~67% más rápido que secuencial
Max Concurrent: 3 (Wave 1)
```

### Dependency Matrix

- **1-3**: None (can start immediately) — F1-F4, 3
- **F1-F4**: 1, 2, 3 — user okay, 0

### Agent Dispatch Summary

- **Wave 1**: **3** — T1 → `quick`, T2 → `quick`, T3 → `writing`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Añadir servicio sqlite-web a docker-compose.yml

  **What to do**:
  - Leer el `docker-compose.yml` actual para entender la estructura exacta
  - Añadir nuevo servicio `sqlite-web` **después** del servicio `gaelcarebot` existente (sin modificarlo)
  - Usar la imagen `coleifer/sqlite-web:latest`
  - Configurar variables:
    - `container_name: gaelcarebot-sqlite-web`
    - `restart: unless-stopped` (igual que gaelcarebot)
    - `volumes: - ./data:/data` (mismo bind mount que gaelcarebot)
    - `ports: - "127.0.0.1:${SQLITE_WEB_PORT:-8080}:8080"` (solo localhost del host, no expuesto)
    - `env_file: - .env`
    - `environment: - SQLITE_WEB_PASSWORD=${SQLITE_WEB_PASSWORD}`
    - `user: "1000:1000"` (mismo UID que `appuser` en Dockerfile de gaelcarebot)
    - `depends_on: - gaelcarebot` (iniciar después del bot)
    - `logging:` con `max-size: "10m"` y `max-file: "3"`
  - Comando: `sqlite_web -H 0.0.0.0 -p 8080 /data/milk.db -P -x`
    - `-H 0.0.0.0`: escuchar en todas las interfaces (necesario para Tailscale)
    - `-P`: leer contraseña de `SQLITE_WEB_PASSWORD` (no prompt interactivo)
    - `-x`: no abrir navegador
  - Añadir healthcheck: `CMD wget -q --spider http://localhost:8080/ || exit 1`

  **Must NOT do**:
  - NO modificar el servicio `gaelcarebot` existente (ni una línea)
  - NO usar `ports: - "8080:8080"` (eso expondría en 0.0.0.0 del host)
  - NO añadir servicios adicionales (nginx, backup, etc.)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Cambio en un solo archivo YAML, estructura conocida, sin lógica compleja
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: None (can start immediately)

  **References**:
  - `docker-compose.yml:1-9` — Estructura actual del servicio gaelcarebot (patrón a seguir para restart, volumes, env_file)
  - `Dockerfile:4,22` — `RUN useradd --create-home appuser` y `RUN chown appuser:appuser /data` — UID del appuser es 1000 por defecto
  - `.env.example:1-6` — Formato de variables de entorno existentes (mantener consistencia)
  - `https://github.com/coleifer/sqlite-web/blob/master/sqlite_web/sqlite_web.py:1652` — Código que confirma `SQLITE_WEB_PASSWORD` env var (línea 1652-1654)
  - `https://hub.docker.com/r/coleifer/sqlite-web` — Documentación de la imagen Docker

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Happy path - servicio sqlite-web arranca y responde
    Tool: Bash
    Preconditions:
      - .env contiene SQLITE_WEB_PASSWORD con valor no vacío
      - gaelcarebot ya está corriendo (o se levanta con depends_on)
      - Puerto 8080 libre en el host
    Steps:
      1. Ejecutar: docker compose up -d
      2. Esperar 5 segundos: sleep 5
      3. Verificar estado: docker compose ps --format json | python3 -c "import sys,json; [print(json.loads(l)['Service'], json.loads(l)['State']) for l in sys.stdin]"
      4. Assert: sqlite-web aparece con State "running"
      5. Verificar logs: docker compose logs sqlite-web 2>&1 | grep -q "Running on"
      6. Assert exit code 0 (encontró "Running on")
    Expected Result:
      - docker compose ps muestra sqlite-web como "running"
      - Logs contienen "Running on http://0.0.0.0:8080"
    Failure Indicators:
      - docker compose ps muestra "exited" o "restarting"
      - Logs contienen "Error" o traceback
      - Puerto 8080 ya en uso (error "address already in use")
    Evidence: .sisyphus/evidence/task-1-service-up.txt
  ```

  ```
  Scenario: Failure - servicio rechaza acceso sin contraseña
    Tool: Bash
    Preconditions:
      - sqlite-web corriendo en puerto 8080
      - SQLITE_WEB_PASSWORD configurado en .env
    Steps:
      1. Ejecutar: curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
      2. Assert: HTTP status code es 302 (redirect a /login/) o 401
    Expected Result: Sin credenciales, el acceso es denegado (redirect a login o 401)
    Failure Indicators:
      - HTTP 200 sin pedir autenticación → la contraseña no está funcionando
      - Connection refused → el servicio no está corriendo
    Evidence: .sisyphus/evidence/task-1-auth-denied.txt
  ```

  ```
  Scenario: Edge case - servicio responde healthcheck
    Tool: Bash
    Preconditions:
      - sqlite-web corriendo
    Steps:
      1. Ejecutar: docker compose exec sqlite-web wget -q --spider http://localhost:8080/
      2. Assert: exit code 0 (wget exit 0 = HTTP 200 OK)
    Expected Result: El healthcheck interno responde correctamente
    Failure Indicators: exit code != 0
    Evidence: .sisyphus/evidence/task-1-healthcheck.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-1-service-up.txt` — output de `docker compose ps`
  - [ ] `.sisyphus/evidence/task-1-auth-denied.txt` — output de curl sin auth
  - [ ] `.sisyphus/evidence/task-1-healthcheck.txt` — output de wget healthcheck

  **Commit**: YES (groups with N/A — single commit)
  - Message: `feat(docker): add sqlite-web service for DB browser access`
  - Files: `docker-compose.yml`
  - Pre-commit: `docker compose config --quiet` (validar sintaxis YAML)

- [x] 2. Actualizar .env.example con variables de sqlite-web

  **What to do**:
  - Leer `.env.example` actual
  - Añadir dos nuevas variables al final del archivo:
    - `SQLITE_WEB_PASSWORD=` (con comentario explicativo)
    - `SQLITE_WEB_PORT=8080` (con comentario explicativo)
  - Mantener el formato existente: `VARIABLE=valor` sin espacios alrededor del `=`
  - Añadir comentarios en español explicando cada variable
  - No alterar las variables existentes ni su orden

  **Must NOT do**:
  - NO modificar variables existentes (BOT_TOKEN, AUTHORIZED_USER_IDS, etc.)
  - NO cambiar el orden de las variables existentes
  - NO añadir valores de ejemplo que parezcan reales
  - NO incluir el valor real de la contraseña (solo placeholder vacío)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Añadir 2 líneas + comentarios a un archivo de configuración
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: F1, F4
  - **Blocked By**: None (can start immediately)

  **References**:
  - `.env.example:1-6` — Formato y estilo de las variables existentes (patrón a copiar)
  - `docker-compose.yml:8` — Línea `env_file: - .env` (confirma que se usa .env)
  - `gaelcarebot/config.py:23-24` — Defaults de DB_PATH y timezone (referencia de estilo de comentarios)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Happy path - variables existen con comentarios
    Tool: Bash
    Preconditions: .env.example existe
    Steps:
      1. Ejecutar: grep -n "SQLITE_WEB_PASSWORD" .env.example
      2. Assert: output contiene al menos una línea con "SQLITE_WEB_PASSWORD=" (sin valor)
      3. Ejecutar: grep -n "SQLITE_WEB_PORT" .env.example  
      4. Assert: output contiene "SQLITE_WEB_PORT=8080"
      5. Ejecutar: grep -c "^BOT_TOKEN=" .env.example
      6. Assert: output es "1" (BOT_TOKEN sigue existiendo, no fue alterado)
    Expected Result:
      - Ambas variables existen en el archivo
      - SQLITE_WEB_PORT tiene valor por defecto 8080
      - SQLITE_WEB_PASSWORD está vacío (placeholder)
      - Variables originales intactas
    Failure Indicators:
      - Alguna variable no encontrada
      - Variables originales modificadas o eliminadas
    Evidence: .sisyphus/evidence/task-2-env-vars.txt
  ```

  ```
  Scenario: Edge case - docker compose reconoce las variables
    Tool: Bash
    Preconditions: .env.example contiene las nuevas variables
    Steps:
      1. Crear .env temporal copiando .env.example: cp .env.example .env.test
      2. Añadir contraseña de prueba: echo "SQLITE_WEB_PASSWORD=test123" >> .env.test
      3. Ejecutar: docker compose --env-file .env.test config 2>&1 | grep SQLITE_WEB_PASSWORD
      4. Assert: output contiene "test123" (el valor es leído por docker compose)
      5. Limpiar: rm .env.test
    Expected Result: docker compose lee correctamente la variable del .env
    Failure Indicators:
      - docker compose config falla con error
      - La variable no aparece en la salida
    Evidence: .sisyphus/evidence/task-2-docker-config.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-2-env-vars.txt` — output de grep mostrando las variables
  - [ ] `.sisyphus/evidence/task-2-docker-config.txt` — output de docker compose config

  **Commit**: YES (groups with Task 1)
  - Message: `feat(docker): add sqlite-web service for DB browser access`
  - Files: `.env.example`
  - Pre-commit: `grep -q "SQLITE_WEB_PASSWORD=" .env.example && grep -q "SQLITE_WEB_PORT=" .env.example`

- [x] 3. Documentar acceso sqlite-web en README.md

  **What to do**:
  - Leer `README.md` actual para entender la estructura de secciones
  - Añadir nueva sección `## Acceso a la base de datos (sqlite-web)` después de la sección `## Notificaciones al grupo`
  - La sección debe incluir:
    - Explicación breve de qué es sqlite-web y para qué sirve
    - Requisito: tener Tailscale configurado en la VPS y en el dispositivo cliente
    - Instrucciones para configurar `.env`: añadir `SQLITE_WEB_PASSWORD` y opcionalmente `SQLITE_WEB_PORT`
    - URL de acceso: `http://<ip-tailscale-de-la-vps>:8080` (o `<hostname>.ts.net:8080` si usa MagicDNS)
    - Nota de seguridad: "La base de datos NO está expuesta a internet. Solo accesible vía Tailscale."
    - Advertencia: "No dejes la sesión abierta indefinidamente — puede interferir con el checkpoint de WAL."
  - Usar placeholders obvios: `tu_contraseña_segura`, `100.XX.XX.XX`, NO usar valores que parezcan reales

  **Must NOT do**:
  - NO incluir valores reales de contraseña o IPs
  - NO reestructurar secciones existentes del README
  - NO modificar el contenido de otras secciones
  - NO añadir secciones sobre backup, nginx, SSL, o Datasette

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentación técnica, traducción al español, mantener consistencia con el estilo del README existente
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: F1, F3, F4
  - **Blocked By**: None (can start immediately)

  **References**:
  - `README.md` — Estructura completa del README (secciones, formato, estilo de escritura en español)
  - `README.md` sección `## Notificaciones al grupo` — Estilo de documentación de features (formato de tablas, viñetas)
  - `README.md` sección `## Despliegue con Docker (recomendado)` — Referencia de comandos Docker documentados
  - `docker-compose.yml` (post-modificación) — Valores exactos de puerto y configuración a documentar

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Happy path - sección sqlite-web existe y es correcta
    Tool: Bash
    Preconditions: README.md ha sido modificado
    Steps:
      1. Ejecutar: grep -n "sqlite-web" README.md
      2. Assert: output contiene al menos 3 líneas (la sección está presente y es sustancial)
      3. Ejecutar: grep -n "SQLITE_WEB_PASSWORD" README.md
      4. Assert: output menciona la variable de contraseña
      5. Ejecutar: grep -n "tailscale\|Tailscale\|ts.net" README.md
      6. Assert: output menciona Tailscale como método de acceso
      7. Ejecutar: grep -n "ip-tailscale\|<hostname>\|XX.XX" README.md
      8. Assert: output usa placeholders, no IPs reales
    Expected Result:
      - Existe una sección "Acceso a la base de datos" o similar
      - Menciona sqlite-web, Tailscale, SQLITE_WEB_PASSWORD
      - Usa placeholders para valores sensibles
      - Incluye advertencia de seguridad
    Failure Indicators:
      - Sección no encontrada o vacía
      - Contiene IPs o contraseñas reales
      - No menciona Tailscale
    Evidence: .sisyphus/evidence/task-3-readme-section.txt
  ```

  ```
  Scenario: Edge case - contenido original del README intacto
    Tool: Bash
    Preconditions: README.md ha sido modificado
    Steps:
      1. Ejecutar: grep -c "^##" README.md
      2. Assert: el número de secciones (líneas que empiezan con ##) es al menos el original (verificar contra versión pre-modificación)
      3. Ejecutar: grep -n "^## Despliegue con Docker" README.md
      4. Assert: la sección existe (no fue eliminada)
      5. Ejecutar: grep -n "^## Comandos del bot" README.md
      6. Assert: la sección existe (no fue eliminada)
    Expected Result: Las secciones existentes permanecen intactas; la nueva sección es adicional
    Failure Indicators: Secciones originales eliminadas o movidas
    Evidence: .sisyphus/evidence/task-3-readme-intact.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-3-readme-section.txt` — grep de la nueva sección
  - [ ] `.sisyphus/evidence/task-3-readme-intact.txt` — grep de secciones originales

  **Commit**: YES (groups with Task 1 and 2 — todos en un solo commit)
  - Message: `feat(docker): add sqlite-web service for DB browser access`
  - Files: `README.md`
  - Pre-commit: `grep -q "sqlite-web" README.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. Verify: 1) `docker-compose.yml` contains exactly one new service `sqlite-web` (no other services modified). 2) `.env.example` contains `SQLITE_WEB_PASSWORD` and `SQLITE_WEB_PORT`. 3) `README.md` contains sqlite-web documentation section. 4) Must NOT HAVE: gaelcarebot service modified, ports exposed publicly (check for `- "8080:8080"` without `127.0.0.1` binding), no nginx/SSL configs added. 5) Evidence files exist in `.sisyphus/evidence/`.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Validate: 1) `docker compose config --quiet` returns exit 0 (valid YAML syntax). 2) No hardcoded secrets in any file (search for passwords, tokens, real-looking IPs). 3) Indentation consistent in YAML files. 4) Markdown formatting valid in README.md. 5) No commented-out code or debug configurations. 6) Placeholders used instead of real values in documentation.
  Output: `Config [PASS/FAIL] | Secrets [CLEAN/ISSUES] | Format [PASS/FAIL] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from Tasks 1-3:
  1. Task 1: docker compose up, verify running, verify auth denied, verify healthcheck.
  2. Task 2: verify .env.example variables, verify docker compose reads them.
  3. Task 3: verify README section exists, verify original content intact.
  Test cross-task integration: gaelcarebot must still respond while sqlite-web is running (concurrent DB access).
  Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (`git diff`). Verify 1:1 — everything in spec was built, nothing beyond spec was built (no creep). Check "Must NOT do" compliance per task. Detect cross-task contamination: Task 1 touching files from Task 2/3 scope (should NOT happen). Flag unaccounted changes. Verify only 3 files changed: `docker-compose.yml`, `.env.example`, `README.md`.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Single commit** (all 3 tasks grouped): `feat(docker): add sqlite-web service for DB browser access`
  - Files: `docker-compose.yml`, `.env.example`, `README.md`
  - Pre-commit: `docker compose config --quiet && grep -q "SQLITE_WEB_PASSWORD=" .env.example && grep -q "sqlite-web" README.md`

---

## Success Criteria

### Verification Commands
```bash
# 1. Servicio arranca correctamente
docker compose up -d && docker compose ps | grep sqlite-web | grep running

# 2. Contraseña protege el acceso
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep -E "302|401"

# 3. Acceso autenticado funciona
curl -s -u :$SQLITE_WEB_PASSWORD -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep "200"

# 4. GaelCareBot sigue operativo (consulta concurrente)
docker compose exec gaelcarebot python -c "from gaelcarebot.db import MilkDatabase; db = MilkDatabase('/data/milk.db'); print('OK:', db.conn.execute('SELECT 1').fetchone())"

# Expected output for all: exit code 0
```

### Final Checklist
- [ ] All "Must Have" (5 items) present
- [ ] All "Must NOT Have" (6 items) absent
- [ ] `docker compose config --quiet` passes
- [ ] sqlite-web responde en `http://localhost:8080`
- [ ] Acceso sin contraseña es denegado
- [ ] GaelCareBot funciona concurrentemente con sqlite-web
