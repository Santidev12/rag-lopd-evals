"""Informe de evaluación estático: una sola página HTML con los números y las 50 preguntas.

Es el demo del proyecto. Un chat en vivo tardaría ~20 s por respuesta y depende de claves y de un
servidor; esto se abre desde un fichero, se publica en GitHub Pages y enseña lo que importa: qué
mide el sistema, qué falla y por qué. Todo sale de ficheros ya guardados (una pasada de
`generacion evaluar`, sus juicios, el recall de `retrieval evaluar --guardar`): construir el
informe no llama a ningún modelo ni cuesta dinero.

La página es autocontenida (sin JavaScript ni recursos externos) y todo lo que viene de datos, en
particular lo que contestó el modelo, se escapa: es texto de un LLM, no HTML de confianza.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from html import escape

from rag_lopd.eval.modelo import EvalSet, Pregunta, TipoPregunta
from rag_lopd.generacion.evaluacion import Latencia, Observacion, Proporcion, resumir
from rag_lopd.generacion.juez import Juicio, Veredicto, resumir_juicios
from rag_lopd.generacion.modelo import Tarifa
from rag_lopd.retrieval.evaluacion import RecallMedido

_NOMBRE_PASADA = re.compile(r"^(?P<modelo>.+)-prompt(?P<prompt>v\d+)-k(?P<k>\d+)-\d{8}-\d{6}")
_NOMBRE_JUICIOS = re.compile(r"\.juez-(?P<juez>.+)-(?P<rubrica>[^-]+)$")

_ETIQUETA_TIPO = {
    TipoPregunta.FACTUAL: "factual",
    TipoPregunta.CRUZADA: "cruzada",
    TipoPregunta.TEMPORAL: "temporal",
    TipoPregunta.FUERA_DE_CORPUS: "fuera de corpus",
    TipoPregunta.TRAMPA: "trampa",
}


def _num(valor: float, decimales: int = 1) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def _pct(p: Proporcion) -> str:
    return f"{_num(p.valor * 100)} %"


def _ic(p: Proporcion) -> str:
    bajo, alto = p.intervalo
    return f"IC 95 %: {bajo * 100:.0f} % a {alto * 100:.0f} %"


def _segundos(valor: float) -> str:
    return f"{_num(valor)} s"


def _e(texto: object) -> str:
    return escape(str(texto), quote=True)


# --- veredicto por pregunta ---------------------------------------------------------------------


def _veredicto(obs: Observacion, juicio: Juicio | None) -> tuple[str, str]:
    """(clase CSS, texto) de lo que pasó con una pregunta: lo que ve quien la hizo.

    Callar bien, contestar bien y contestar con una cita que cubre la fuente cuentan como `ok`.
    Sobre-respuesta, abstención indebida y contenido incorrecto cuentan como `falla`; un contenido
    parcial es `aviso`. Si no hay juicio, una respondible contestada queda `sin-juzgar`: no se
    inventa un acierto que nadie comprobó.
    """
    if obs.debe_abstenerse:
        if obs.respuesta.se_abstiene:
            return "ok", "Se calló, como debía"
        if juicio is not None and juicio.veredicto is Veredicto.INCORRECTA:
            return "falla", "Sobre-respuesta grave: afirma algo que la norma no sostiene"
        return "falla", "Sobre-respuesta: contestó sin respuesta en el corpus"
    if obs.respuesta.se_abstiene:
        return "falla", "Abstención indebida: calló teniendo la respuesta"
    if juicio is None:
        return "sin-juzgar", "Contestó (contenido sin juzgar)"
    if juicio.veredicto is Veredicto.CORRECTA:
        return "ok", "Contestó correctamente"
    if juicio.veredicto is Veredicto.PARCIAL:
        return "aviso", "Contestó, pero la respuesta es parcial"
    if juicio.veredicto is Veredicto.INCORRECTA:
        return "falla", "Contestó, pero el contenido es incorrecto"
    return "aviso", "Contestó (el juez no devolvió un veredicto válido)"


# --- piezas de HTML -----------------------------------------------------------------------------


def _tarjeta(titulo: str, valor: str, detalle: str, pista: str = "") -> str:
    return (
        '<div class="tarjeta">'
        f'<div class="tarjeta-titulo">{_e(titulo)}</div>'
        f'<div class="tarjeta-valor">{_e(valor)}</div>'
        f'<div class="tarjeta-detalle">{_e(detalle)}</div>'
        + (f'<div class="tarjeta-pista">{_e(pista)}</div>' if pista else "")
        + "</div>"
    )


def _tabla(cabecera: list[str], filas: Iterable[list[str]]) -> str:
    """`filas` ya trae el HTML de cada celda: quien llama escapa lo que haga falta."""
    encabezado = "".join(f"<th>{_e(c)}</th>" for c in cabecera)
    cuerpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in fila) + "</tr>" for fila in filas)
    return (
        f'<div class="tabla"><table><thead><tr>{encabezado}</tr></thead>'
        f"<tbody>{cuerpo}</tbody></table></div>"
    )


def _celda_proporcion(p: Proporcion) -> str:
    return f"{p.exitos}/{p.casos} · <strong>{_e(_pct(p))}</strong> <small>({_e(_ic(p))})</small>"


def _seccion_numeros(
    observaciones: list[Observacion],
    juicios: dict[str, Juicio] | None,
    tarifa: Tarifa,
) -> str:
    resumen = resumir(observaciones)
    tarjetas = [
        _tarjeta(
            "Sobre-respuesta",
            _pct(resumen.sobre_respuesta),
            f"{resumen.sobre_respuesta.exitos}/{resumen.sobre_respuesta.casos} · "
            f"{_ic(resumen.sobre_respuesta)}",
            "Contesta sin tener la respuesta en el corpus. El fallo caro.",
        ),
        _tarjeta(
            "Abstención indebida",
            _pct(resumen.abstencion_indebida),
            f"{resumen.abstencion_indebida.exitos}/{resumen.abstencion_indebida.casos} · "
            f"{_ic(resumen.abstencion_indebida)}",
            "Calla teniendo la respuesta. El fallo espejo: se reporta siempre junto al anterior.",
        ),
    ]
    if juicios is not None:
        exactitud = resumir_juicios(observaciones, juicios).exactitud
        tarjetas.append(
            _tarjeta(
                "Exactitud",
                _pct(exactitud),
                f"{exactitud.exitos}/{exactitud.casos} · {_ic(exactitud)}",
                "Respondibles contestadas correctamente según el juez. Callar cuenta como fallo.",
            )
        )
    tarjetas.append(
        _tarjeta(
            "Cita cubre la fuente",
            _pct(resumen.cita_cubre_fuente),
            f"{resumen.cita_cubre_fuente.exitos}/{resumen.cita_cubre_fuente.casos} · "
            f"{_ic(resumen.cita_cubre_fuente)}",
            "De las contestadas, las que citan todos los artículos de la fuente esperada.",
        )
    )
    if observaciones:
        coste = tarifa.coste_usd(resumen.uso) / len(observaciones)
        tarjetas.append(
            _tarjeta(
                "Coste por consulta",
                f"{_num(coste, 4)} $",
                f"{resumen.uso.tokens_entrada} tokens de entrada en {len(observaciones)} consultas",
            )
        )
    if resumen.latencia is not None:
        tarjetas.append(
            _tarjeta(
                "Latencia p50 / p95",
                f"{_segundos(resumen.latencia.p50_s)} / {_segundos(resumen.latencia.p95_s)}",
                f"{resumen.latencia.consultas} consultas, extremo a extremo",
            )
        )

    por_tipo = [
        [
            _e(_ETIQUETA_TIPO[tipo]),
            _celda_proporcion(resumen.comportamiento_por_tipo[tipo]),
        ]
        for tipo in TipoPregunta
        if resumen.comportamiento_por_tipo[tipo].casos
    ]
    html = f'<div class="tarjetas">{"".join(tarjetas)}</div>'
    html += (
        "<h3>Comportamiento correcto por tipo de pregunta</h3>"
        "<p>Callar si no hay respuesta en el corpus, contestar si la hay.</p>"
        + _tabla(["Tipo", "Aciertos"], por_tipo)
    )
    if resumen.salidas_invalidas:
        html += (
            f'<p class="aviso-texto">{resumen.salidas_invalidas} salida(s) del modelo sin el JSON '
            "pedido: contaminan las cifras de arriba.</p>"
        )
    return html


def _seccion_retrieval(recall: list[RecallMedido]) -> str:
    """Denso, sin ruta jerárquica: la variante elegida en el ticket 11."""
    elegidos = [r for r in recall if r.motor == "denso" and not r.con_ruta]
    if not elegidos:
        return "<p>El fichero de recall no trae medidas del motor denso sin ruta jerárquica.</p>"
    ks = sorted({r.k for r in elegidos})
    filas = []
    for nivel, nombre in (("articulo", "Artículo correcto"), ("apartado", "Apartado exacto")):
        por_k = {r.k: r for r in elegidos if r.nivel == nivel}
        celdas = [
            f"{por_k[k].aciertos}/{por_k[k].total} · <strong>"
            f"{_e(_num(por_k[k].aciertos / por_k[k].total * 100 if por_k[k].total else 0))} %"
            "</strong>"
            if k in por_k
            else "—"
            for k in ks
        ]
        filas.append([_e(nombre), *celdas])
    fallos = {r.k: r.fallos for r in elegidos if r.nivel == "articulo" and r.fallos}
    html = (
        "<p>De las preguntas factuales y cruzadas, en cuántas aparece entre los k primeros "
        "resultados lo que hacía falta (en una cruzada, <em>todos</em> los artículos). "
        "El generador recibe el artículo entero, así que la medida que predice si tendrá el texto "
        "delante es la de artículo.</p>" + _tabla(["Recall"] + [f"@{k}" for k in ks], filas)
    )
    if fallos:
        detalle = " · ".join(f"@{k}: {_e(', '.join(ids))}" for k, ids in sorted(fallos.items()))
        html += (
            "<p><small>Preguntas sin su artículo en el top-k (nivel artículo): "
            f"{detalle}</small></p>"
        )
    return html


def _fila_latencia(nombre: str, latencia: Latencia | None) -> list[str]:
    if latencia is None:
        return [_e(nombre), "—", "—", "—"]
    return [
        _e(nombre),
        _e(_segundos(latencia.p50_s)),
        _e(_segundos(latencia.p95_s)),
        str(latencia.consultas),
    ]


def _seccion_latencia(observaciones: list[Observacion]) -> str:
    resumen = resumir(observaciones)
    if resumen.latencia is None:
        return ""
    filas = [_fila_latencia("Extremo a extremo", resumen.latencia)]
    if resumen.latencia_recuperacion and resumen.latencia_generacion:
        filas.append(_fila_latencia("Recuperar (embeber + buscar)", resumen.latencia_recuperacion))
        filas.append(
            _fila_latencia("Generar (modelo, con reintentos)", resumen.latencia_generacion)
        )
        nota = ""
    else:
        nota = (
            "<p><small>Esta pasada es anterior al desglose: se sabe lo que tarda en total, no "
            "cuánto es recuperar y cuánto generar.</small></p>"
        )
    return (
        "<p>Una sola pasada de 50 consultas: con tan pocas, el p95 es casi el máximo. Incluye los "
        "reintentos por límite de uso o tiempo de espera, que es lo que vería un usuario.</p>"
        + _tabla(["Tramo", "p50", "p95", "Consultas"], filas)
        + nota
    )


def _lista(ids: Iterable[object]) -> str:
    valores = [_e(i) for i in ids]
    return ", ".join(f"<code>{v}</code>" for v in valores) if valores else "—"


def _pregunta(pregunta: Pregunta, obs: Observacion, juicio: Juicio | None, *, abierta: bool) -> str:
    clase, etiqueta = _veredicto(obs, juicio)
    respuesta = obs.respuesta
    if respuesta.texto and respuesta.responde:
        dicho = f'<p class="cita-texto">{_e(respuesta.texto)}</p>'
    elif respuesta.se_abstiene:
        dicho = "<p><em>Se abstuvo de contestar.</em></p>"
    else:
        dicho = f'<p class="cita-texto">{_e(respuesta.texto)}</p>'

    filas = [
        ("Respuesta de referencia", f"<p>{_e(pregunta.respuesta)}</p>"),
        ("Fuente esperada", _lista(pregunta.fuente)),
        ("Artículos entregados al modelo", _lista(obs.contextos)),
        ("Respuesta del sistema", dicho),
        ("Citas", _lista(respuesta.citas)),
    ]
    if not obs.debe_abstenerse:
        llego = obs.fuente_articulos <= {str(c) for c in obs.contextos}
        filas.insert(
            3,
            ("¿Llegó la fuente al modelo?", "Sí" if llego else "No: el fallo es de recuperación"),
        )
    if juicio is not None:
        motivo = f" — {_e(juicio.motivo)}" if juicio.motivo else ""
        filas.append(("Juez", f"<strong>{_e(juicio.veredicto.value)}</strong>{motivo}"))
    if obs.latencia_s is not None:
        filas.append(("Latencia", _e(_segundos(obs.latencia_s))))
    if pregunta.notas:
        filas.append(("Notas del eval set", f"<p>{_e(pregunta.notas)}</p>"))

    detalle = "".join(f"<dt>{_e(k)}</dt><dd>{v}</dd>" for k, v in filas)
    return (
        f'<details class="q q-{clase}" id="{_e(pregunta.id)}"{" open" if abierta else ""}>'
        "<summary>"
        f'<span class="q-id">{_e(pregunta.id)}</span>'
        f'<span class="q-tipo">{_e(_ETIQUETA_TIPO[pregunta.tipo])}</span>'
        f'<span class="q-texto">{_e(pregunta.pregunta)}</span>'
        f'<span class="q-estado estado-{clase}">{_e(etiqueta)}</span>'
        f"</summary><dl>{detalle}</dl></details>"
    )


_CSS = """
:root {
  --fondo: #fbfaf8; --superficie: #ffffff; --texto: #1d1c1a; --suave: #5f5b55;
  --linea: #e3dfd8; --acento: #2f5d8a; --ok: #2d7a4b; --aviso: #9a6a00; --falla: #b3372b;
  --ok-fondo: #e6f3ea; --aviso-fondo: #fbf1d9; --falla-fondo: #f8e4e1; --neutro-fondo: #eceae5;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --fondo: #161513; --superficie: #1f1d1b; --texto: #ece9e3; --suave: #aaa49a;
    --linea: #34312d; --acento: #8fb6e0; --ok: #6cc590; --aviso: #e2b95a; --falla: #ee8b80;
    --ok-fondo: #1c2f23; --aviso-fondo: #342b14; --falla-fondo: #3a1f1c; --neutro-fondo: #2a2825;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--fondo); color: var(--texto);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 62rem; margin: 0 auto; padding: 2rem 16px 4rem; }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 0 0 .5rem; }
h2 { font-size: 1.3rem; margin: 2.8rem 0 .6rem; padding-top: 1rem;
  border-top: 1px solid var(--linea); }
h3 { font-size: 1.05rem; margin: 1.6rem 0 .3rem; }
p { margin: .5rem 0; }
small, .meta { color: var(--suave); }
code { font: .85em ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--neutro-fondo);
  padding: .1em .35em; border-radius: 4px; }
.entradilla { font-size: 1.1rem; max-width: 46rem; }
.meta { font-size: .9rem; margin-top: .8rem; }
.tarjetas { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 12px;
  margin: 1.2rem 0; }
.tarjeta { background: var(--superficie); border: 1px solid var(--linea); border-radius: 10px;
  padding: 14px 16px; }
.tarjeta-titulo { font-size: .85rem; color: var(--suave); }
.tarjeta-valor { font-size: 1.8rem; font-weight: 650; line-height: 1.2; margin: .15rem 0; }
.tarjeta-detalle { font-size: .85rem; }
.tarjeta-pista { font-size: .8rem; color: var(--suave); margin-top: .4rem; }
.tabla { overflow-x: auto; margin: .6rem 0; }
table { border-collapse: collapse; width: 100%; background: var(--superficie);
  border: 1px solid var(--linea); border-radius: 8px; }
th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--linea);
  vertical-align: top; }
th { font-size: .85rem; color: var(--suave); font-weight: 600; }
tr:last-child td { border-bottom: 0; }
.q { background: var(--superficie); border: 1px solid var(--linea); border-left-width: 4px;
  border-radius: 8px; margin: 8px 0; }
.q-ok { border-left-color: var(--ok); } .q-aviso { border-left-color: var(--aviso); }
.q-falla { border-left-color: var(--falla); } .q-sin-juzgar { border-left-color: var(--suave); }
.q summary { cursor: pointer; padding: 10px 14px; display: grid; gap: 4px 10px;
  grid-template-columns: auto auto 1fr; align-items: baseline; }
.q-id { font-weight: 650; } .q-tipo { color: var(--suave); font-size: .85rem; }
.q-texto { grid-column: 1 / -1; }
.q-estado { grid-column: 1 / -1; font-size: .85rem; font-weight: 600; }
.estado-ok { color: var(--ok); } .estado-aviso { color: var(--aviso); }
.estado-falla { color: var(--falla); } .estado-sin-juzgar { color: var(--suave); }
.q dl { margin: 0; padding: 4px 14px 14px; display: grid; gap: 2px 14px;
  grid-template-columns: 1fr; }
.q dt { font-size: .8rem; color: var(--suave); margin-top: .6rem; }
.q dd { margin: 0; overflow-wrap: anywhere; }
.cita-texto { white-space: pre-wrap; background: var(--neutro-fondo); padding: .6rem .8rem;
  border-radius: 6px; }
.aviso-texto { color: var(--falla); font-weight: 600; }
ul.limites { padding-left: 1.2rem; } ul.limites li { margin: .4rem 0; }
@media (min-width: 640px) {
  .q summary { grid-template-columns: auto auto 1fr auto; }
  .q-texto { grid-column: auto; } .q-estado { grid-column: auto; text-align: right; }
  .q dl { grid-template-columns: 13rem 1fr; } .q dt { margin-top: 0; padding-top: .45rem; }
}
"""


def construir_informe(
    observaciones: list[Observacion],
    eval_set: EvalSet,
    *,
    modelo: str,
    tarifa: Tarifa,
    nombre_pasada: str,
    fecha: date,
    juicios: dict[str, Juicio] | None = None,
    nombre_juicios: str | None = None,
    recall: list[RecallMedido] | None = None,
) -> str:
    """El informe completo como una cadena HTML. Determinista: mismos datos, misma página."""
    por_id = {p.id: p for p in eval_set.preguntas}
    desconocidas = sorted(o.pregunta_id for o in observaciones if o.pregunta_id not in por_id)
    if desconocidas:
        raise ValueError(f"preguntas de la pasada que no están en el eval set: {desconocidas}")

    pasada = _NOMBRE_PASADA.match(nombre_pasada)
    configuracion = f"Modelo <code>{_e(modelo)}</code>"
    if pasada:
        configuracion += (
            f" · prompt <code>{_e(pasada['prompt'])}</code> · k=<code>{_e(pasada['k'])}</code>"
        )
    juez = _NOMBRE_JUICIOS.search(nombre_juicios.removesuffix(".jsonl")) if nombre_juicios else None
    if juez:
        configuracion += (
            f" · juez <code>{_e(juez['juez'])}</code> (rúbrica <code>{_e(juez['rubrica'])}</code>)"
        )

    sin_respuesta = sum(1 for o in observaciones if o.debe_abstenerse)
    ordenadas = sorted(observaciones, key=lambda o: o.pregunta_id)
    visibles = [(por_id[o.pregunta_id], o, (juicios or {}).get(o.pregunta_id)) for o in ordenadas]
    problemas = [(p, o, j) for p, o, j in visibles if _veredicto(o, j)[0] in ("falla", "aviso")]

    partes = [
        "<!doctype html>",
        '<html lang="es"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Informe de evaluación del RAG de protección de datos</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<h1>Un RAG sobre protección de datos que sabe cuándo callarse</h1>",
        '<p class="entradilla">Responde preguntas concretas sobre el RGPD y la LOPDGDD citando el '
        "artículo exacto, y se abstiene cuando la respuesta no está en el corpus. Esta página es "
        f"el informe de su evaluación sobre {len(observaciones)} preguntas: lo que acierta, lo "
        "que falla y lo que cuesta, con cada pregunta a la vista.</p>",
        f'<p class="meta">{configuracion} · {len(observaciones)} preguntas · '
        f"generado el {fecha.isoformat()} desde <code>{_e(nombre_pasada)}</code></p>",
        "<h2>Los números</h2>",
        _seccion_numeros(observaciones, juicios, tarifa),
    ]
    if recall:
        partes += ["<h2>Recuperación</h2>", _seccion_retrieval(recall)]
    latencia = _seccion_latencia(observaciones)
    if latencia:
        partes += ["<h2>Latencia</h2>", latencia]
    partes += [
        f"<h2>Dónde falla ({len(problemas)})</h2>",
        "<p>Cada pregunta en la que el sistema se equivoca o contesta a medias, abierta, con lo "
        "que se le dio al modelo y lo que dijo.</p>"
        if problemas
        else "<p>Ninguna pregunta falla en esta pasada.</p>",
        *[_pregunta(p, o, j, abierta=True) for p, o, j in problemas],
        f"<h2>Las {len(visibles)} preguntas</h2>",
        "<p>Pulsa una para ver la referencia, la fuente esperada y lo que contestó el sistema.</p>",
        *[_pregunta(p, o, j, abierta=False) for p, o, j in visibles],
        "<h2>Cómo leer estas cifras</h2>",
        '<ul class="limites">'
        f"<li>Son de <strong>una sola pasada</strong> (un modelo, un prompt). Con {sin_respuesta} "
        "preguntas sin respuesta, un solo caso mueve la sobre-respuesta varios puntos: por eso van "
        "con intervalo de confianza, y los intervalos son anchos.</li>"
        + (
            "<li>La exactitud la mide un <strong>juez automático</strong> de otra familia que el "
            "generador, contrastado con una revisión manual. Es algo más estricto que una "
            "persona.</li>"
            if juicios is not None
            else ""
        )
        + "<li>El eval set se construyó con ayuda de un LLM y todas las preguntas se revisaron a "
        "mano. Se corrigió una a posteriori (e-047), y eso <strong>no es una mejora del "
        "sistema</strong>. El método y las correcciones están en "
        "<code>docs/eval-set.md</code>.</li>"
        "<li>Los fallos de las preguntas sin respuesta que el sistema calló no los ve el juez: una "
        "referencia mal puesta de ese estilo pasaría desapercibida.</li>"
        "</ul>",
        "</main></body></html>",
    ]
    return "\n".join(partes) + "\n"
