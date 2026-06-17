=== sqlite-web mentions ===
4
116:## Acceso a la base de datos (sqlite-web)
118:El proyecto incluye [sqlite-web](https://github.com/coleifer/sqlite-web), un navegador web ligero para SQLite que permite consultar y editar la base de datos desde el navegador.
120:**Requisito**: Tener [Tailscale](https://tailscale.com/) configurado en la VPS y en tu dispositivo cliente.
127:# Contrasena para acceder a sqlite-web (obligatorio)
128:SQLITE_WEB_PASSWORD=tu_contrasena_segura
131:SQLITE_WEB_PORT=8080
151:http://<hostname>.ts.net:8080
154:Introduce la contrasena configurada en `SQLITE_WEB_PASSWORD`.
158:- La base de datos **NO esta expuesta a internet**. Solo es accesible a traves de tu red privada Tailscale.
160:- No dejes la sesion de sqlite-web abierta indefinidamente -- puede interferir con el checkpoint automatico de WAL de SQLite.
