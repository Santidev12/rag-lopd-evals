# Esqueleto del repo y tooling de Python

Type: task
Status: resolved

## Question

Dejar el repo listo para escribir código el mismo día: repositorio git público en GitHub,
gestor de dependencias y entorno, layout de paquetes, linter/formatter, pytest, gestión de
secretos y licencia. Incluye las decisiones de tooling (que se toman sobre la marcha, no en
un ticket aparte) y un primer commit.

Criterio de hecho: `pytest` corre en verde con un test trivial, el linter pasa, y hay un
commit inicial empujado a un repositorio público.

## Progreso (sesión del 7-sep-2026)

Hecho por mí, en `AI/rag-lopd-evals/` (movido fuera del taller de lecciones para que la carpeta
se llame igual que el repo):

- `pyproject.toml` con uv: httpx, lxml, pydantic, pydantic-settings, typer; dev con pytest,
  respx, ruff y mypy. TOML validado.
- Layout `src/rag_lopd/` con `config.py` (pydantic-settings, fuentes del corpus ya fijadas con la
  evidencia de `docs/research/`) y `cli.py` (typer, comando `info`). Sintaxis validada.
- `tests/test_config.py` con 4 tests.
- ruff como linter y formateador, mypy con `disallow_untyped_defs`, CI en GitHub Actions.
- `.gitignore` (incluye `.env`, `data/` y `.scratch/`), `.gitattributes`, `.env.example`, LICENSE MIT,
  README con el esqueleto de las cuatro preguntas y los huecos de las cifras.
- `git init` + primer commit `2841460` en la rama `main`.

Pendiente de Santiago (necesita red y Windows, el puente no tiene ninguna de las dos):
1. Borrar la carpeta `_to_delete/`.
2. `uv sync` y comprobar que `uv run pytest` va en verde.
3. Crear el repo público `rag-lopd-evals` en GitHub y `git push -u origin main`.
4. Commitear el `uv.lock` que genere `uv sync`.

**Aprendizaje operativo**: no ejecutar git desde el puente con su equipo. Cada comando deja un
`.git/index.lock` que el montaje no permite borrar y que bloquea los commits siguientes.

## Answer

Resuelto el 13-sep-2026. Santiago confirma `uv sync` y `uv run pytest` en verde en su Windows.

Stack fijado: **uv** (entorno, dependencias y versión del intérprete en un solo binario, con `uv.lock`
para builds reproducibles) · layout **`src/`** (obliga a que los tests importen el paquete instalado,
así un fichero que falte en el paquete falla igual en local que en el despliegue) · **pydantic-settings**
para la configuración (valida y castea en el borde; las claves con `repr=False`) · **typer** para la CLI,
expuesta como comando `rag-lopd` · **ruff** como linter y formateador · **mypy** con
`disallow_untyped_defs` · **CI en GitHub Actions** con los cuatro pasos.

Commit inicial `2841460` en `main`. **Pendiente y no bloqueante**: crear el repo en GitHub, `git push`
y commitear el `uv.lock`.

**Aprendizaje operativo**: no ejecutar git desde el puente con su equipo — el montaje no permite borrar
y cada comando deja un `.git/index.lock` que bloquea los commits siguientes.
