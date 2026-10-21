"""Descarga con caché en disco y manifiesto de procedencia.

Dos reglas que parecen burocracia y no lo son:

1. **Se descarga una vez.** El corpus no cambia entre ejecuciones, y machacar a golpe de peticiones
   los servidores del BOE o de la Oficina de Publicaciones es mala educación y una forma rápida de
   que te bloqueen.
2. **Se apunta de dónde salió cada fichero, cuándo y con qué huella.** El README va a publicar unos
   números; sin esto no puedes demostrar sobre qué texto los mediste. Es la diferencia entre un
   resultado y una anécdota.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


class Descargador:
    """Trae ficheros de la red y los deja cacheados en un directorio."""

    NOMBRE_MANIFIESTO = "manifest.json"

    def __init__(
        self,
        directorio: Path,
        *,
        timeout: float = 30.0,
        user_agent: str = "rag-lopd-evals/0.1",
    ) -> None:
        self.directorio = directorio
        self.timeout = timeout
        self.user_agent = user_agent

    @property
    def ruta_manifiesto(self) -> Path:
        return self.directorio / self.NOMBRE_MANIFIESTO

    def obtener(
        self,
        url: str,
        nombre: str,
        *,
        forzar: bool = False,
        acepta: str | None = None,
    ) -> Path:
        """Devuelve la ruta local del fichero, descargándolo solo si hace falta.

        `acepta` fija la cabecera Accept. No es opcional para todo el mundo: la API del BOE
        responde 400 "No soportado ningún mime type de la cabecera Accept" ante el `*/*` que
        mandan curl y httpx por defecto.
        """
        destino = self.directorio / nombre
        if destino.exists() and not forzar:
            return destino

        self.directorio.mkdir(parents=True, exist_ok=True)
        cabeceras = {"User-Agent": self.user_agent}
        if acepta is not None:
            cabeceras["Accept"] = acepta
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as cliente:
            respuesta = cliente.get(url, headers=cabeceras)
            respuesta.raise_for_status()
            contenido = respuesta.content

        destino.write_bytes(contenido)
        self._anotar(nombre, url, contenido)
        return destino

    def _anotar(self, nombre: str, url: str, contenido: bytes) -> None:
        manifiesto = self.leer_manifiesto()
        manifiesto[nombre] = {
            "url": url,
            "descargado_en": datetime.now(UTC).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(contenido).hexdigest(),
            "bytes": len(contenido),
        }
        self.ruta_manifiesto.write_text(
            json.dumps(manifiesto, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def leer_manifiesto(self) -> dict[str, dict[str, object]]:
        if not self.ruta_manifiesto.exists():
            return {}
        datos: dict[str, dict[str, object]] = json.loads(
            self.ruta_manifiesto.read_text(encoding="utf-8")
        )
        return datos
