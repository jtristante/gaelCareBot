# Release Workflow — GaelCareBot

Documentacion del sistema de versionado, release, deploy y rollback del proyecto.

## Versionado

El proyecto usa un formato de version inspirado en Maven SNAPSHOT:

```
X.Y.Z.dev0
```

- **X (MAJOR)**: incrementa en cada release.
- **Y (MINOR)**: incrementa al preparar el siguiente ciclo de desarrollo tras un release.
- **Z (PATCH)**: reservado para hotfixes (no se usa actualmente).
- **`.dev0`**: indica que es una version de desarrollo. Una imagen SNAPSHOT se publica como `:latest` y se sobrescribe en cada push a `master`.

### Reglas de bump

| Evento | Bump | Ejemplo (desde) | Ejemplo (resultado) |
|---|---|---|---|
| Release | MAJOR +1, quitar `.dev0` | `0.1.0.dev0` | `1.0.0` |
| Post-release | MINOR +1, anadir `.dev0` | `1.0.0` | `1.1.0.dev0` |
| Push a master | Ninguno (sigue siendo SNAPSHOT) | `0.1.0.dev0` | `0.1.0.dev0` |

### Tabla de transformaciones

| Version actual | Accion | Version resultante | Tag Docker |
|---|---|---|---|
| `0.1.0.dev0` | Release | `1.0.0` | `ghcr.io/jtristante/gaelcarebot:1.0.0` |
| `1.0.0` | Post-release | `1.1.0.dev0` | `:latest` |
| `1.1.0.dev0` | Release | `2.0.0` | `ghcr.io/jtristante/gaelcarebot:2.0.0` |
| `2.0.0` | Hotfix (hipotetico) | `2.0.1` | `ghcr.io/jtristante/gaelcarebot:2.0.1` |
| `2.0.1` | Post-hotfix | `2.1.0.dev0` | `:latest` |

La version se lee del archivo `VERSION` en la raiz del repositorio. Ese archivo es la fuente de verdad.

## Flujo de release

### Ejecucion

El release se dispara manualmente desde GitHub Actions:

1. Ir a `https://github.com/jtristante/gaelcarebot/actions`
2. Seleccionar el workflow **Release** en la barra lateral
3. Clic en **Run workflow** (workflow_dispatch)
4. Confirmar con la rama `master`

### Que hace el workflow

El workflow Release ejecuta estos pasos de forma automatica:

```
 1. Stash          — guarda cambios locales sin commitear (si los hay)
 2. Leer version   — extrae el contenido de VERSION
 3. Validar        — comprueba que termina en .dev0
 4. Calcular       — quita .dev0, incrementa MAJOR
 5. Escribir       — guarda la nueva version release en VERSION
 6. Commit         — "Release X.0.0"
 7. Tag            — git tag vX.0.0
 8. Calcular next  — incrementa MINOR, anade .dev0
 9. Escribir       — guarda la nueva version SNAPSHOT en VERSION
10. Commit         — "Bump to X.Y.0.dev0"
11. Push           — git push --follow-tags
12. Restore stash  — recupera cambios sin commitear (si los hay)
```

### Pipeline completo

```
         workflow_dispatch (manual)
                    |
               [Release workflow]
                    |
            +-----v------+
            |  Commit     |  "Release 1.0.0"
            |  Tag        |  v1.0.0
            |  Bump dev   |  "Bump to 1.1.0.dev0"
            +-----+------+
                  |
            git push --follow-tags
                  |
            +-----v------+
            |  CI (tag)   |  .github/workflows/ci.yml
            |  - test     |
            |  - build    |
            |  - push     |  ghcr.io/.../gaelcarebot:1.0.0
            +-----+------+
                  |
            +-----v------+
            |  Deploy     |  .github/workflows/deploy.yml
            |  - pull     |
            |  - restart  |
            |  - health   |
            |  - prune    |
            +-----+------+
                  |
            VPS actualizado
```

El tag push (`v*`) activa el job `build-and-push` de CI, que ademas de `:latest` genera las tags semver (`1.0.0`, `1.0`). El deploy se dispara tanto por CI exitoso como por tag push.

## Sistema de deploy

### Dos modos de imagen

| Tag | Cuando se genera | Persistencia | Uso |
|---|---|---|---|
| `:latest` | Cada push a `master` | Efimera (se sobrescribe) | Desarrollo continuo |
| `:X.0.0` (semver) | Cada release (tag `v*`) | Persistente (no se sobrescribe) | Releases estables |

### Comportamiento de `docker image prune -f`

El paso de cleanup en deploy ejecuta `docker image prune -f`, que elimina imagenes **dangling** (sin tag). Las imagenes taggeadas (`:1.0.0`, `:latest`) no se eliminan.

### Que imagenes quedan en el VPS

| Escenario | Imagenes en disco |
|---|---|
| Desarrollo normal (push a master) | `:latest`, mas las ultimas layers en cache de buildx |
| Release `v1.0.0` | `:latest`, `:1.0.0`, `:1.0` |
| Release `v2.0.0` posterior | `:latest`, `:1.0.0`, `:1.0`, `:2.0.0`, `:2.0` |
| Tras `docker image prune -f` | Solo las taggeadas (las dangling se limpian) |

Las imagenes de releases anteriores (`:1.0.0`) permanecen en disco y pueden usarse para rollback sin descargar nada.

## Rollback

### Comando exacto

Para volver a una version anterior, edita `docker-compose.prod.yml` en el VPS y reinicia:

```bash
sed -i 's/:latest/:1.0.0/' /opt/gaelcarebot/docker-compose.prod.yml
cd /opt/gaelcarebot && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

O, de forma mas directa, especificando la imagen exacta:

```bash
docker compose -f /opt/gaelcarebot/docker-compose.yml \
              -f /opt/gaelcarebot/docker-compose.prod.yml \
              up -d
```

(Asegurate de que `docker-compose.prod.yml` referencie la imagen deseada antes de ejecutar.)

### La imagen ya esta en disco

Cuando se hizo el deploy original de la release, la imagen quedo almacenada localmente. No es necesario descargarla de nuevo. Verifica que la imagen existe:

```bash
docker images ghcr.io/jtristante/gaelcarebot
```

Salida esperada:

```
REPOSITORY                          TAG       IMAGE ID       CREATED       SIZE
ghcr.io/jtristante/gaelcarebot      1.0.0     abc123def456   2 days ago    215MB
ghcr.io/jtristante/gaelcarebot      latest    def789abc012   1 hour ago    215MB
```

### Verificacion post-rollback

```bash
# Comprobar que el contenedor se reinicio correctamente
docker compose -f /opt/gaelcarebot/docker-compose.yml \
              -f /opt/gaelcarebot/docker-compose.prod.yml \
              ps

# Verificar healthcheck
docker inspect --format='{{.State.Health.Status}}' gaelcarebot

# Revisar logs
docker compose -f /opt/gaelcarebot/docker-compose.yml \
              -f /opt/gaelcarebot/docker-compose.prod.yml \
              logs --tail=20
```

### Restaurar latest tras rollback

Si el rollback fue temporal y quieres volver a `:latest`:

```bash
sed -i 's/:1.0.0/:latest/' /opt/gaelcarebot/docker-compose.prod.yml
cd /opt/gaelcarebot && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Ejemplos practicos

### Escenario completo: de desarrollo a release y rollback

Partimos de:

```
VERSION = 0.1.0.dev0
```

**Paso 1: Ejecutar el workflow Release en GitHub Actions**

Desde la interfaz de GitHub Actions, seleccionar workflow "Release" y hacer clic en "Run workflow".

**Paso 2: El workflow ejecuta automaticamente**

```
Leer VERSION        → "0.1.0.dev0"
Calcular release    → "1.0.0"
Commit              → "Release 1.0.0"
Tag                 → v1.0.0
Calcular next       → "1.1.0.dev0"
Commit              → "Bump to 1.1.0.dev0"
Push                → git push --follow-tags
```

Resultado en el repositorio:

```
$ cat VERSION
1.1.0.dev0

$ git tag --list 'v*'
v1.0.0
```

**Paso 3: CI construye la imagen**

Al pushear el tag `v1.0.0`, CI se activa. El job `build-and-push` genera:

- `ghcr.io/jtristante/gaelcarebot:1.0.0`
- `ghcr.io/jtristante/gaelcarebot:1.0`

**Paso 4: Deploy automatico**

Deploy recoge el evento y actualiza el VPS:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull gaelcarebot
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
# Espera healthcheck...
# Prune de imagenes dangling
```

**Paso 5: Algo falla en produccion, hay que hacer rollback**

En el VPS:

```bash
# Ver las imagenes disponibles
docker images ghcr.io/jtristante/gaelcarebot

# Volver a 1.0.0
sed -i 's/:latest/:1.0.0/' /opt/gaelcarebot/docker-compose.prod.yml
cd /opt/gaelcarebot && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verificar que funciona
docker inspect --format='{{.State.Health.Status}}' gaelcarebot
```

**Paso 6: El fix esta listo, restaurar latest**

```bash
sed -i 's/:1.0.0/:latest/' /opt/gaelcarebot/docker-compose.prod.yml
cd /opt/gaelcarebot && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Que pasa si hay cambios sin commitear

El workflow Release comienza con un `git stash`. Si tienes cambios locales sin commitear en la rama `master`:

1. Se guardan automaticamente con `git stash`
2. El workflow ejecuta los commits de release y bump
3. Al finalizar, restaura los cambios con `git stash pop`

Esto evita commits mezclados. Si hay conflictos al hacer pop, el workflow falla y los cambios quedan en el stash. Recuperalos manualmente:

```bash
git stash list
git stash pop
```
