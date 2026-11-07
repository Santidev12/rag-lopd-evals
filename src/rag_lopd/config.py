"""Configuración del proyecto.

Todo lo que cambia entre máquinas o entre entornos vive aquí, y solo aquí.
`Settings` lee, por este orden de prioridad: variables de entorno del proceso,
luego el fichero `.env`, y si no hay nada, los valores por defecto de abajo.

Se instancia una sola vez (`get_settings()`) para no releer el `.env` en cada llamada.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Fuentes del corpus -------------------------------------------------
    boe_api_base: str = "https://www.boe.es/datosabiertos/api"
    """API de legislación consolidada del BOE. Sin auth, sin rate limit observado."""

    boe_lopdgdd_id: str = "BOE-A-2018-16673"
    """Identificador de la LOPDGDD (Ley Orgánica 3/2018)."""

    cellar_base: str = "http://publications.europa.eu/resource/celex"
    """Cellar, no eur-lex.europa.eu.

    EUR-Lex responde con un reto JS de AWS WAF a cualquier cliente que no sea un navegador.
    """

    rgpd_celex: str = "02016R0679-20160504"
    """CELEX del RGPD consolidado.

    Sin el 0 inicial sería el acto original, que sí trae los 173 considerandos.
    """

    # --- Rutas --------------------------------------------------------------
    data_dir: Path = Path("data")
    """Descargas y corpus normalizado. Está en .gitignore: se regenera con `rag-lopd ingest`."""

    # --- Red ----------------------------------------------------------------
    http_timeout_seconds: float = 30.0
    user_agent: str = "rag-lopd-evals/0.1 (proyecto de portfolio; contacto en el README)"
    """Identificarse es de buena educación y evita bloqueos. Nunca lo dejes en el de la librería."""

    # --- Azure OpenAI (sin clave: se autentica con Entra ID) -----------------
    azure_openai_endpoint: str | None = None
    """URL del recurso, p. ej. `https://mi-recurso.openai.azure.com`. No es un secreto."""

    azure_openai_deployment: str | None = None
    """Nombre del **despliegue** del modelo (no el del modelo): es lo que va en la URL de la
    llamada."""

    azure_openai_api_version: str = "2024-10-21"
    """Versión de la API de Azure OpenAI. Sin verificar contra la documentación: ajústala aquí si el
    servicio la rechaza."""

    # --- Azure AI Search (sin clave por defecto: se autentica con clave o con Entra ID) ---
    azure_search_endpoint: str | None = None
    """URL del servicio, p. ej. `https://<servicio>.search.windows.net`. No es un secreto."""

    azure_search_index: str = "rag-lopd-v0"
    """Nombre del índice. Uno solo: cubre las cuatro configuraciones de Azure
    (vectorial, exacto, BM25 e híbrido)."""

    # --- Claves (nunca con valor por defecto real: van en .env) --------------
    deepinfra_api_key: str | None = Field(default=None, repr=False)
    google_api_key: str | None = Field(default=None, repr=False)
    azure_search_api_key: str | None = Field(default=None, repr=False)

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración, cacheada. Usa `get_settings.cache_clear()` en tests."""
    return Settings()
