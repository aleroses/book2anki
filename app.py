"""Interfaz Streamlit para elegir párrafos y guardarlos como tarjetas."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import API_MODELO, EXPORT_DIR, OLLAMA_MODELO, PROVEEDOR, RAM_GB
from db import (
    actualizar_tarjeta,
    borrar_fuente,
    borrar_tarjetas,
    borrar_todas_las_tarjetas,
    contar_tarjetas_de,
    crear_tarjeta,
    fuentes_con_rutas,
    guardar_enriquecimiento,
    guardar_resumen,
    inicializar,
    leer_resumen,
    listar_fuentes,
    listar_secciones,
    listar_tarjetas,
    obtener_seccion,
    restablecer_todo,
    textos_de_seccion,
)
from enriquecedores import resumir_seccion, sugerir_tarjetas, usar_proveedor
from exporter import exportar_tsv
from importers import (
    ErrorImportacion,
    codigo_de_parrafo,
    detectar_idioma,
    importar_plan,
    partir_parrafos,
    planificar_importacion,
    texto_sin_vallas,
)
from models import ENRIQUECEDORES, Card, Enriquecedor, ErrorEnriquecimiento, Section
from providers import ErrorProveedor, proveedor_desde_config

_CAMPOS_EDITABLES = (
    "title",
    "subtitle",
    "notes",
    "tags",
    "original_text",
    "code",
    "code_lang",
)
_MODELO_GRANDE = re.compile(r"(\d+)\s*b", re.IGNORECASE)
_CAMPOS_ENRIQUECIDOS = ("translation", "explanation")
_ORDEN_TABLA = (
    "borrar",
    "generar",
    "id",
    "title",
    "source",
    "chapter",
    "subtitle",
    "lang",
    "original_text",
    "translation",
    "explanation",
    "code",
    "code_lang",
    "notes",
    "tags",
)
_GENERAR_TRADUCCION = ("traductor",)
_GENERAR_EXPLICACION = ("explicador",)
_GENERAR_TODO = ("traductor", "explicador", "subtitulador")


def main() -> None:
    """Arranca la página: barra lateral y cuatro pestañas."""
    st.set_page_config(page_title="Book2Anki", layout="wide")
    inicializar()
    st.session_state.setdefault("editor_version", 0)
    st.session_state.setdefault("ajustes_version", 0)
    st.title("Book2Anki")
    st.caption("Elige los párrafos que quieres convertir en tarjetas.")
    aviso_ajustes = st.session_state.pop("aviso_ajustes", None)
    if aviso_ajustes:
        st.success(aviso_ajustes)
    fuente_id, seccion_id = barra_lateral()
    tab_lectura, tab_tarjetas, tab_exportar, tab_ajustes = st.tabs(
        ["Lectura", "Mis tarjetas", "Exportar", "Ajustes"],
        key="pestanas",
        on_change="rerun",
    )
    with tab_lectura:
        pintar_lectura(seccion_id)
    with tab_tarjetas:
        # El editor mide mal el ancho si se pinta con la pestaña oculta.
        if tab_tarjetas.open:
            pintar_tarjetas()
    with tab_exportar:
        pintar_exportar()
    with tab_ajustes:
        pintar_ajustes(fuente_id)


def barra_lateral() -> tuple[int | None, int | None]:
    """Importa una ruta y devuelve la fuente y la sección elegidas."""
    st.sidebar.header("Fuentes")
    with st.sidebar.form("importar"):
        ruta = st.text_input(
            "Ruta del archivo o carpeta",
            placeholder="ejemplos/notas_ejemplo.md",
        )
        enviar = st.form_submit_button("Importar fuente")
    if enviar:
        _preparar_importacion(ruta)
    _pintar_decision_reimportar()
    aviso = st.session_state.pop("aviso", None)
    if aviso:
        st.sidebar.success(aviso)

    fuentes = listar_fuentes()
    if not fuentes:
        st.sidebar.info("Todavía no hay fuentes importadas.")
        return None, None

    ids = [fuente.id for fuente in fuentes]
    nombres = {fuente.id: f"{fuente.name} (#{fuente.id})" for fuente in fuentes}
    if st.session_state.get("fuente_sel") not in ids:
        st.session_state["fuente_sel"] = ids[0]
    fuente_id = st.sidebar.selectbox(
        "Fuente",
        ids,
        format_func=nombres.get,
        key="fuente_sel",
    )

    secciones = listar_secciones(fuente_id)
    if not secciones:
        st.sidebar.warning("Esta fuente no tiene secciones.")
        return fuente_id, None
    ids_seccion = [seccion.id for seccion in secciones if seccion.id is not None]
    etiquetas = {
        seccion.id: f"{seccion.position + 1}. {seccion.heading}"
        for seccion in secciones
        if seccion.id is not None
    }
    if st.session_state.get("seccion_sel") not in ids_seccion:
        st.session_state["seccion_sel"] = ids_seccion[0]
    seccion_id = st.sidebar.selectbox(
        "Sección",
        ids_seccion,
        format_func=etiquetas.get,
        key="seccion_sel",
    )
    return fuente_id, seccion_id


def pintar_lectura(seccion_id: int | None) -> None:
    """Muestra la sección y las tarjetas propuestas, en dos columnas."""
    if seccion_id is None:
        st.info("Importa una fuente y elige una sección para empezar.")
        return
    seccion = obtener_seccion(seccion_id)
    if seccion is None:
        st.warning("No se encontró la sección.")
        return
    izquierda, derecha = st.columns(2)
    with izquierda:
        _pintar_navegacion(seccion)
        with st.container(height=640, border=True):
            _pintar_cuerpo(seccion)
    with derecha:
        with st.container(height=640, border=True):
            _pintar_estudio(seccion)


def pintar_tarjetas() -> None:
    """Tabla editable de tarjetas, con guardado, borrado y generación."""
    aviso = st.session_state.pop("aviso_ia", None)
    if aviso:
        st.info(aviso)
    tarjetas = listar_tarjetas()
    if not tarjetas:
        st.info("Aún no has añadido tarjetas.")
        return
    originales = {tarjeta.id: tarjeta for tarjeta in tarjetas if tarjeta.id is not None}
    editado = st.data_editor(
        _tabla_tarjetas(tarjetas),
        disabled=["id", "source", "chapter", "lang"],
        column_order=_ORDEN_TABLA,
        column_config={
            "borrar": st.column_config.CheckboxColumn(
                "Borrar", default=False, width="small"
            ),
            "generar": st.column_config.CheckboxColumn(
                "Generar", default=False, width="small"
            ),
            "id": st.column_config.NumberColumn("id", pinned=True),
            "source": st.column_config.TextColumn("source"),
            "chapter": st.column_config.TextColumn("chapter"),
            "title": st.column_config.TextColumn("title", pinned=True),
            "subtitle": st.column_config.TextColumn("subtitle"),
            "lang": st.column_config.TextColumn("lang"),
            "original_text": st.column_config.TextColumn(
                "original_text", width="large"
            ),
            "translation": st.column_config.TextColumn("translation", width="large"),
            "explanation": st.column_config.TextColumn("explanation", width="large"),
            "code": st.column_config.TextColumn("code", width="large"),
            "code_lang": st.column_config.TextColumn("code_lang"),
            "notes": st.column_config.TextColumn("notes"),
            "tags": st.column_config.TextColumn("tags"),
        },
        hide_index=True,
        num_rows="fixed",
        key=f"editor-{st.session_state['editor_version']}",
    )
    sobrescribir = st.checkbox(
        "Sobrescribir las que ya tienen texto",
        key="sobrescribir_ia",
    )
    regenerar = st.checkbox("Regenerar ignorando caché", key="regenerar_ia")
    columna_trad, columna_expl, columna_todo = st.columns(3)
    with columna_trad:
        if st.button("Generar traducción"):
            _generar(editado, originales, _GENERAR_TRADUCCION, sobrescribir, regenerar)
    with columna_expl:
        if st.button("Generar explicación"):
            _generar(editado, originales, _GENERAR_EXPLICACION, sobrescribir, regenerar)
    with columna_todo:
        if st.button("Generar todo"):
            _generar(editado, originales, _GENERAR_TODO, sobrescribir, regenerar)
    columna_guardar, columna_borrar = st.columns(2)
    with columna_guardar:
        if st.button("Guardar cambios"):
            _guardar_edicion(editado, originales)
    with columna_borrar:
        if st.button("Borrar seleccionadas"):
            _borrar_marcadas(editado)


def pintar_ajustes(fuente_id: int | None) -> None:
    """Proveedor de texto y borrados confirmados."""
    st.subheader("Ajustes")
    _pintar_modelo()
    st.divider()
    version = st.session_state["ajustes_version"]
    _pintar_borrar_tarjetas(version)
    st.divider()
    _pintar_borrar_fuente(fuente_id, version)
    st.divider()
    _pintar_restablecer(version)


def pintar_exportar() -> None:
    """Genera un TSV y ofrece descargarlo."""
    st.write(
        "El archivo usa UTF-8. Los saltos de línea pasan a `<br>` "
        "y los tabuladores internos a espacios."
    )
    if st.button("Generar TSV"):
        _generar_tsv()
    ruta = st.session_state.get("ultimo_tsv")
    if not ruta:
        return
    archivo = Path(ruta)
    if not archivo.is_file():
        return
    st.success(f"Archivo creado: {archivo}")
    st.download_button(
        "Descargar TSV",
        data=archivo.read_bytes(),
        file_name=archivo.name,
        mime="text/tab-separated-values",
    )


def _preparar_importacion(ruta: str) -> None:
    """Importa si la ruta es nueva. Si ya existe, deja la decisión en sesión."""
    st.session_state.pop("reimportar", None)
    try:
        plan = planificar_importacion(ruta)
    except ErrorImportacion as exc:
        st.sidebar.error(str(exc))
        return
    paths = [str(path) for path, _kind, _nombre in plan]
    existentes = fuentes_con_rutas(paths)
    if not existentes:
        _ejecutar_importacion(plan, reemplazar=False)
        return
    st.session_state["reimportar"] = {
        "plan": [(str(path), kind, nombre) for path, kind, nombre in plan],
        "fuentes": len(existentes),
        "tarjetas": contar_tarjetas_de([fuente.id for fuente in existentes]),
    }


def _pintar_decision_reimportar() -> None:
    """Pregunta si se reemplazan las fuentes ya importadas o se añade otra copia."""
    decision = st.session_state.get("reimportar")
    if not decision:
        return
    st.sidebar.warning(
        f"Ya hay {decision['fuentes']} fuente(s) con esta ruta "
        f"y {decision['tarjetas']} tarjeta(s). "
        "Reemplazar borra esas fuentes y sus tarjetas."
    )
    columna_reemplazar, columna_otra = st.sidebar.columns(2)
    with columna_reemplazar:
        reemplazar = st.button("Reemplazar", key="reimportar_reemplazar")
    with columna_otra:
        otra = st.button("Añadir otra", key="reimportar_otra")
    plan = [
        (Path(ruta), kind, nombre)
        for ruta, kind, nombre in decision["plan"]
    ]
    if reemplazar:
        _ejecutar_importacion(plan, reemplazar=True)
    elif otra:
        _ejecutar_importacion(plan, reemplazar=False)


def _ejecutar_importacion(
    plan: list[tuple[Path, str, str]], reemplazar: bool
) -> None:
    """Inserta el plan. Si reemplazar, antes borra las fuentes con el mismo path."""
    try:
        if reemplazar:
            paths = [str(path) for path, _kind, _nombre in plan]
            for fuente in fuentes_con_rutas(paths):
                borrar_fuente(fuente.id)
        ids = importar_plan(plan)
    except ErrorImportacion as exc:
        st.sidebar.error(str(exc))
        return
    except (sqlite3.Error, RuntimeError, OSError) as exc:
        st.sidebar.error(f"No se pudo importar: {exc}")
        return
    st.session_state.pop("reimportar", None)
    st.session_state["aviso"] = f"Se importaron {len(ids)} fuente(s)."
    if ids:
        st.session_state["fuente_sel"] = ids[-1]
    st.session_state["editor_version"] += 1
    st.rerun()


def _pintar_borrar_tarjetas(version: int) -> None:
    st.markdown("**Borrar todas las tarjetas**")
    st.caption("Las fuentes y las secciones se quedan.")
    confirmar = st.checkbox(
        "Entiendo que no se puede deshacer",
        key=f"conf_tarjetas-{version}",
    )
    if st.button("Borrar todas las tarjetas", disabled=not confirmar):
        try:
            total = borrar_todas_las_tarjetas()
        except sqlite3.Error as exc:
            st.error(f"No se pudieron borrar las tarjetas: {exc}")
            return
        _avisar_ajustes(f"Se borraron {total} tarjetas.")


def _pintar_borrar_fuente(fuente_id: int | None, version: int) -> None:
    st.markdown("**Borrar fuente seleccionada**")
    fuente = next(
        (item for item in listar_fuentes() if item.id == fuente_id),
        None,
    )
    if fuente is None:
        st.caption("No hay ninguna fuente seleccionada.")
        st.button("Borrar fuente seleccionada", disabled=True)
        return
    tarjetas = contar_tarjetas_de([fuente.id])
    st.caption(
        f"{fuente.name}: {tarjetas} tarjeta(s). También se borran sus secciones."
    )
    confirmar = st.checkbox(
        "Entiendo que no se puede deshacer",
        key=f"conf_fuente-{version}",
    )
    if st.button("Borrar fuente seleccionada", disabled=not confirmar):
        try:
            secciones, borradas = borrar_fuente(fuente.id)
        except (sqlite3.Error, RuntimeError) as exc:
            st.error(f"No se pudo borrar la fuente: {exc}")
            return
        st.session_state.pop("reimportar", None)
        _avisar_ajustes(
            f"Se borró 1 fuente, {secciones} secciones y {borradas} tarjetas."
        )


def _pintar_restablecer(version: int) -> None:
    st.markdown("**Restablecer todo**")
    st.caption("Vacía las tres tablas y reinicia los identificadores.")
    borrar_archivos = st.checkbox(
        "Borrar también los archivos de data/exportaciones/",
        key=f"conf_export-{version}",
    )
    confirmar = st.checkbox(
        "Entiendo que no se puede deshacer",
        key=f"conf_reset-{version}",
    )
    if st.button("Restablecer todo", disabled=not confirmar):
        try:
            fuentes, secciones, tarjetas = restablecer_todo()
            archivos = _vaciar_exportaciones() if borrar_archivos else None
        except (sqlite3.Error, OSError, RuntimeError) as exc:
            st.error(f"No se pudo restablecer: {exc}")
            return
        st.session_state.pop("reimportar", None)
        st.session_state.pop("ultimo_tsv", None)
        mensaje = (
            f"Se borraron {fuentes} fuentes, {secciones} secciones "
            f"y {tarjetas} tarjetas."
        )
        if archivos is not None:
            mensaje += f" Se eliminaron {archivos} archivos de exportación."
        _avisar_ajustes(mensaje)


def _vaciar_exportaciones() -> int:
    """Borra los archivos de EXPORT_DIR. El directorio se recrea al exportar."""
    if not EXPORT_DIR.is_dir():
        return 0
    archivos = [path for path in EXPORT_DIR.iterdir() if path.is_file()]
    for archivo in archivos:
        archivo.unlink()
    try:
        EXPORT_DIR.rmdir()
    except OSError:
        pass
    return len(archivos)


def _avisar_ajustes(mensaje: str) -> None:
    """Muestra el resultado al recargar y desmarca las confirmaciones."""
    st.session_state["aviso_ajustes"] = mensaje
    st.session_state["ajustes_version"] += 1
    st.session_state["editor_version"] += 1
    st.rerun()


def id_vecino(ids: list[int], actual: int, paso: int) -> int | None:
    """Devuelve el id anterior (paso -1) o siguiente (paso 1), o None en el extremo."""
    try:
        indice = ids.index(actual)
    except ValueError:
        return None
    destino = indice + paso
    if destino < 0 or destino >= len(ids):
        return None
    return ids[destino]


def _elegir_seccion(section_id: int) -> None:
    """Fija la sección antes de que el selectbox se pinte."""
    st.session_state["seccion_sel"] = section_id


def _pintar_navegacion(seccion: Section) -> None:
    """Cambia la sección elegida según el orden de la fuente."""
    if seccion.source_id is None or seccion.id is None:
        return
    ids = [
        item.id
        for item in listar_secciones(seccion.source_id)
        if item.id is not None
    ]
    if seccion.id not in ids:
        return
    anterior_id = id_vecino(ids, seccion.id, -1)
    siguiente_id = id_vecino(ids, seccion.id, 1)
    anterior, siguiente = st.columns(2)
    with anterior:
        st.button(
            "Anterior",
            disabled=anterior_id is None,
            key="sec-anterior",
            on_click=_elegir_seccion,
            args=(anterior_id,) if anterior_id is not None else (),
        )
    with siguiente:
        st.button(
            "Siguiente",
            disabled=siguiente_id is None,
            key="sec-siguiente",
            on_click=_elegir_seccion,
            args=(siguiente_id,) if siguiente_id is not None else (),
        )


def _pintar_cuerpo(seccion: Section) -> None:
    """Pinta el Markdown, el código y el alta manual de cada párrafo."""
    st.subheader(seccion.heading)
    st.caption(
        "{c} · {t} · {s}".format(
            c=seccion.chapter or "—",
            t=seccion.title or "—",
            s=seccion.subtitle or "—",
        )
    )
    ruta = _ruta_de_fuente(seccion.source_id)
    if ruta:
        st.caption(ruta)
    parrafos = partir_parrafos(seccion.body)
    if not parrafos:
        st.info("Esta sección no tiene párrafos.")
        return
    ya_anadidos = textos_de_seccion(seccion.id) if seccion.id is not None else set()
    for indice, parrafo in enumerate(parrafos):
        _pintar_bloque(parrafo)
        _pintar_boton_anadir(
            seccion, indice, parrafo, parrafo.strip() in ya_anadidos
        )


def _pintar_bloque(parrafo: str) -> None:
    codigo = codigo_de_parrafo(parrafo)
    if codigo is None:
        st.markdown(parrafo)
        return
    lenguaje, interior = codigo
    if lenguaje:
        st.code(interior, language=lenguaje)
        return
    st.code(interior)


def _pintar_boton_anadir(
    seccion: Section, indice: int, parrafo: str, anadido: bool
) -> None:
    if anadido:
        st.caption("Ya en tarjetas")
    if st.button(
        "Añadir a tarjetas",
        key=f"anadir-{seccion.id}-{indice}",
        disabled=anadido,
    ) and _crear_desde_parrafo(seccion, parrafo):
        st.rerun()


def _ruta_de_fuente(source_id: int | None) -> str:
    if source_id is None:
        return ""
    for fuente in listar_fuentes():
        if fuente.id == source_id:
            return fuente.path
    return ""


def _crear_desde_parrafo(seccion: Section, parrafo: str) -> bool:
    """Guarda el párrafo como tarjeta. Devuelve False si no se pudo."""
    if seccion.id is None or seccion.source_id is None:
        st.error("La sección no está guardada en la base.")
        return False
    codigo = codigo_de_parrafo(parrafo)
    code_lang, code = codigo if codigo is not None else ("", "")
    tarjeta = Card(
        source_id=seccion.source_id,
        section_id=seccion.id,
        chapter=seccion.chapter,
        title=seccion.title,
        subtitle=seccion.subtitle,
        lang=detectar_idioma(parrafo),
        original_text=parrafo.strip(),
        code=code,
        code_lang=code_lang,
    )
    try:
        crear_tarjeta(tarjeta)
    except sqlite3.Error as exc:
        st.error(f"No se pudo guardar la tarjeta: {exc}")
        return False
    return True


def _tabla_tarjetas(tarjetas: list[Card]) -> pd.DataFrame:
    filas = [
        {
            "id": tarjeta.id,
            "source": tarjeta.source_name,
            "chapter": tarjeta.chapter,
            "title": tarjeta.title,
            "subtitle": tarjeta.subtitle,
            "lang": tarjeta.lang,
            "original_text": tarjeta.original_text,
            "translation": tarjeta.translation,
            "explanation": tarjeta.explanation,
            "code": tarjeta.code,
            "code_lang": tarjeta.code_lang,
            "notes": tarjeta.notes,
            "tags": tarjeta.tags,
            "generar": False,
            "borrar": False,
        }
        for tarjeta in tarjetas
    ]
    return pd.DataFrame(filas)


def _guardar_edicion(editado: pd.DataFrame, originales: dict[int, Card]) -> None:
    cambios = 0
    try:
        for _, fila in editado.iterrows():
            card_id = int(fila["id"])
            actual = originales[card_id]
            valores = {campo: _texto(fila[campo]) for campo in _CAMPOS_EDITABLES}
            lang = actual.lang
            if valores["original_text"] != actual.original_text:
                lang = detectar_idioma(valores["original_text"])
            enriquecidos = {
                campo: _texto(fila[campo]) for campo in _CAMPOS_ENRIQUECIDOS
            }
            texto_cambio = any(
                valores[campo] != getattr(actual, campo) for campo in _CAMPOS_EDITABLES
            )
            ia_cambio = any(
                enriquecidos[campo] != getattr(actual, campo)
                for campo in _CAMPOS_ENRIQUECIDOS
            )
            if not texto_cambio and not ia_cambio:
                continue
            if texto_cambio:
                actualizar_tarjeta(
                    card_id,
                    valores["title"],
                    valores["subtitle"],
                    valores["notes"],
                    valores["tags"],
                    valores["original_text"],
                    lang,
                    valores["code"],
                    valores["code_lang"],
                )
            if ia_cambio:
                guardar_enriquecimiento(
                    card_id,
                    enriquecidos["translation"],
                    enriquecidos["explanation"],
                )
            cambios += 1
    except sqlite3.Error as exc:
        st.error(f"No se pudieron guardar los cambios: {exc}")
        return
    if cambios == 0:
        st.info("No había cambios que guardar.")
        return
    st.session_state["editor_version"] += 1
    st.rerun()


def _borrar_marcadas(editado: pd.DataFrame) -> None:
    ids = [
        int(fila["id"])
        for _, fila in editado.iterrows()
        if bool(fila["borrar"]) and not _vacio(fila["borrar"])
    ]
    if not ids:
        st.warning("Marca al menos una tarjeta en la columna Borrar.")
        return
    try:
        borrar_tarjetas(ids)
    except sqlite3.Error as exc:
        st.error(f"No se pudieron borrar las tarjetas: {exc}")
        return
    st.session_state["editor_version"] += 1
    st.rerun()


def _pintar_estudio(seccion: Section) -> None:
    """Resumen y tarjetas propuestas. No escribe en cards hasta guardar."""
    if seccion.id is None:
        return
    _pintar_estado_modelo()
    st.divider()
    clave_n = f"n-tarjetas-{seccion.id}"
    if clave_n not in st.session_state:
        st.session_state[clave_n] = sugerir_tarjetas(seccion.body)
    cantidad = int(
        st.number_input(
            "Número de tarjetas",
            min_value=1,
            max_value=3,
            step=1,
            key=clave_n,
        )
    )
    regenerar = st.checkbox(
        "Regenerar ignorando caché",
        key=f"regenerar-resumen-{seccion.id}",
    )
    if st.button("Generar resumen y tarjetas", key=f"generar-resumen-{seccion.id}"):
        _generar_resumen(seccion, cantidad, regenerar)
    estado = _estado_estudio(seccion.id)
    for aviso in estado["avisos"]:
        st.warning(aviso)
    clave_resumen = f"resumen-{seccion.id}-{estado['version']}"
    if clave_resumen not in st.session_state:
        st.session_state[clave_resumen] = estado["resumen"]
    st.text_area("Resumen", key=clave_resumen, height=140)
    if st.button("Guardar resumen", key=f"guardar-resumen-{seccion.id}"):
        _guardar_resumen_editado(seccion.id, clave_resumen, estado)
    for propuesta in list(estado["tarjetas"]):
        _pintar_propuesta(seccion, propuesta, estado)
    if estado["tarjetas"] and st.button(
        "Guardar todas", key=f"guardar-todas-{seccion.id}"
    ):
        _guardar_todas(seccion, estado)


def _estado_estudio(section_id: int) -> dict[str, object]:
    estudios = st.session_state.setdefault("estudio", {})
    if section_id not in estudios:
        estudios[section_id] = {
            "resumen": leer_resumen(section_id) or "",
            "tarjetas": [],
            "avisos": [],
            "version": 0,
            "lang": "",
        }
    return estudios[section_id]


def _generar_resumen(seccion: Section, cantidad: int, regenerar: bool) -> None:
    if seccion.id is None:
        return
    try:
        proveedor = _proveedor_activo()
        lang = detectar_idioma(texto_sin_vallas(seccion.body))
        resultado = resumir_seccion(
            proveedor,
            seccion.body,
            n=cantidad,
            lang=lang,
            regenerar=regenerar,
        )
    except ErrorProveedor as exc:
        st.error(str(exc))
        return
    except ErrorEnriquecimiento as exc:
        st.error(str(exc))
        return
    estado = _estado_estudio(seccion.id)
    version = int(estado["version"]) + 1
    estado["version"] = version
    estado["resumen"] = resultado.resumen
    estado["avisos"] = list(resultado.avisos)
    estado["lang"] = lang
    estado["tarjetas"] = [
        {
            "uid": f"{version}-{indice}",
            "title": tarjeta.title,
            "subtitle": tarjeta.subtitle,
            "original_text": tarjeta.original_text,
            "explanation": tarjeta.explanation,
            "code": tarjeta.code,
            "code_lang": tarjeta.code_lang,
            "translation": tarjeta.translation,
        }
        for indice, tarjeta in enumerate(resultado.tarjetas)
    ]
    st.rerun()


def _guardar_resumen_editado(
    section_id: int, clave: str, estado: dict[str, object]
) -> None:
    texto = str(st.session_state.get(clave, ""))
    try:
        guardar_resumen(section_id, texto)
    except sqlite3.Error as exc:
        st.error(f"No se pudo guardar el resumen: {exc}")
        return
    estado["resumen"] = texto
    st.success("Resumen guardado.")


def _pintar_propuesta(
    seccion: Section, propuesta: dict[str, str], estado: dict[str, object]
) -> None:
    if seccion.id is None:
        return
    uid = propuesta["uid"]
    st.markdown("**Tarjeta propuesta**")
    _campo_estudio(seccion.id, uid, "titulo", "Título", propuesta["title"])
    _campo_estudio(seccion.id, uid, "subtitulo", "Subtítulo", propuesta["subtitle"])
    _campo_estudio(
        seccion.id, uid, "texto", "Texto original", propuesta["original_text"], True
    )
    if estado["lang"] == "en" or propuesta["translation"]:
        _campo_estudio(
            seccion.id,
            uid,
            "traduccion",
            "Traducción",
            propuesta["translation"],
            True,
        )
    _campo_estudio(
        seccion.id, uid, "explicacion", "Explicación", propuesta["explanation"], True
    )
    _campo_estudio(seccion.id, uid, "codigo", "Código", propuesta["code"], True)
    _campo_estudio(seccion.id, uid, "lenguaje", "Lenguaje", propuesta["code_lang"])
    guardar, descartar = st.columns(2)
    with guardar:
        if st.button("Guardar tarjeta", key=f"guardar-{seccion.id}-{uid}"):
            if _guardar_propuesta(seccion, propuesta, estado):
                _quitar_propuesta(estado, uid)
                st.rerun()
    with descartar:
        if st.button("Descartar", key=f"descartar-{seccion.id}-{uid}"):
            _quitar_propuesta(estado, uid)
            st.rerun()


def _campo_estudio(
    section_id: int,
    uid: str,
    nombre: str,
    etiqueta: str,
    defecto: str,
    area: bool = False,
) -> None:
    clave = f"{nombre}-{section_id}-{uid}"
    if clave not in st.session_state:
        st.session_state[clave] = defecto
    if area:
        st.text_area(etiqueta, key=clave, height=100)
        return
    st.text_input(etiqueta, key=clave)


def _guardar_todas(seccion: Section, estado: dict[str, object]) -> None:
    guardadas: list[str] = []
    for propuesta in list(estado["tarjetas"]):  # type: ignore[arg-type]
        if _guardar_propuesta(seccion, propuesta, estado):
            guardadas.append(propuesta["uid"])
    if not guardadas:
        return
    estado["tarjetas"] = [
        tarjeta
        for tarjeta in estado["tarjetas"]  # type: ignore[union-attr]
        if tarjeta["uid"] not in guardadas
    ]
    st.rerun()


def _guardar_propuesta(
    seccion: Section, propuesta: dict[str, str], estado: dict[str, object]
) -> bool:
    if seccion.id is None or seccion.source_id is None:
        st.error("La sección no está guardada en la base.")
        return False
    uid = propuesta["uid"]
    title = _valor_estudio(seccion.id, uid, "titulo").strip()
    original = _valor_estudio(seccion.id, uid, "texto").strip()
    if not title or not original:
        st.error("La tarjeta necesita título y texto original.")
        return False
    lang = str(estado["lang"]) or detectar_idioma(original)
    tarjeta = Card(
        source_id=seccion.source_id,
        section_id=seccion.id,
        chapter=seccion.chapter,
        title=title,
        subtitle=_valor_estudio(seccion.id, uid, "subtitulo").strip(),
        lang=lang,
        original_text=original,
        translation=_valor_estudio(seccion.id, uid, "traduccion").strip(),
        explanation=_valor_estudio(seccion.id, uid, "explicacion").strip(),
        code=_valor_estudio(seccion.id, uid, "codigo"),
        code_lang=_valor_estudio(seccion.id, uid, "lenguaje").strip(),
    )
    try:
        crear_tarjeta(tarjeta)
    except sqlite3.Error as exc:
        st.error(f"No se pudo guardar la tarjeta: {exc}")
        return False
    return True


def _valor_estudio(section_id: int, uid: str, nombre: str) -> str:
    return str(st.session_state.get(f"{nombre}-{section_id}-{uid}", ""))


def _quitar_propuesta(estado: dict[str, object], uid: str) -> None:
    estado["tarjetas"] = [
        tarjeta
        for tarjeta in estado["tarjetas"]  # type: ignore[union-attr]
        if tarjeta["uid"] != uid
    ]


def _pintar_estado_modelo() -> None:
    """Proveedor, modelo y si la última prueba de conexión fue bien."""
    try:
        proveedor = _proveedor_activo()
    except ErrorProveedor as exc:
        st.error(str(exc))
        return
    st.markdown("**Modelo**")
    st.write(f"{proveedor.nombre} · {proveedor.modelo}")
    ok, mensaje = _probar_modelo(proveedor)
    if ok:
        st.success(mensaje)
    else:
        st.error(mensaje)
    if _modelo_grande(proveedor.modelo):
        st.warning(
            f"El modelo {proveedor.modelo} es de 7B o más. "
            f"Con {RAM_GB} GB de RAM puede quedarse corto."
        )


def _probar_modelo(proveedor: object) -> tuple[bool, str]:
    clave = (getattr(proveedor, "nombre", ""), getattr(proveedor, "modelo", ""))
    if st.session_state.get("probe_clave") != clave:
        try:
            st.session_state["probe_msg"] = proveedor.probar()  # type: ignore[attr-defined]
            st.session_state["probe_ok"] = True
        except ErrorProveedor as exc:
            st.session_state["probe_msg"] = str(exc)
            st.session_state["probe_ok"] = False
        st.session_state["probe_clave"] = clave
    return bool(st.session_state["probe_ok"]), str(st.session_state["probe_msg"])


def _modelo_grande(nombre: str) -> bool:
    return any(int(numero) >= 7 for numero in _MODELO_GRANDE.findall(nombre))


def _asegurar_modelo() -> None:
    if "proveedor_sel" not in st.session_state:
        st.session_state["proveedor_sel"] = (
            PROVEEDOR if PROVEEDOR in ("ollama", "api") else "ollama"
        )
    if "modelo_sel" not in st.session_state:
        st.session_state["modelo_sel"] = (
            API_MODELO if st.session_state["proveedor_sel"] == "api" else OLLAMA_MODELO
        )


def _proveedor_activo():
    """El proveedor de la sesión, o el falso si el entorno lo pide."""
    _asegurar_modelo()
    if PROVEEDOR.strip().lower() == "falso":
        return proveedor_desde_config("falso")
    return proveedor_desde_config(
        st.session_state.get("proveedor_sel"),
        st.session_state.get("modelo_sel"),
    )


def _pintar_modelo() -> None:
    """Selector de proveedor y prueba de conexión. La clave no se muestra."""
    st.markdown("**Modelo**")
    _asegurar_modelo()
    st.selectbox("Proveedor", ["ollama", "api"], key="proveedor_sel")
    st.text_input("Modelo", key="modelo_sel")
    st.caption(
        "Ollama usa el equipo local. La API lee BOOK2ANKI_API_URL, "
        "BOOK2ANKI_API_MODEL y BOOK2ANKI_API_KEY del entorno."
    )
    if st.button("Probar conexión"):
        try:
            proveedor = proveedor_desde_config(
                st.session_state["proveedor_sel"],
                st.session_state["modelo_sel"],
            )
            st.success(proveedor.probar())
        except ErrorProveedor as exc:
            st.error(str(exc))


def _generar(
    editado: pd.DataFrame,
    originales: dict[int, Card],
    nombres: tuple[str, ...],
    sobrescribir: bool,
    regenerar: bool,
) -> None:
    """Aplica los enriquecedores a las filas marcadas y guarda las que cambian."""
    ids = _ids_marcados(editado, "generar")
    if not ids:
        st.warning("Marca al menos una tarjeta en la columna Generar.")
        return
    try:
        proveedor = _proveedor_activo()
    except ErrorProveedor as exc:
        st.error(str(exc))
        return
    usar_proveedor(proveedor)
    por_nombre = {item.name: item for item in ENRIQUECEDORES}
    progreso = st.progress(0.0)
    escritas = 0
    omitidas = 0
    errores: list[str] = []
    for indice, card_id in enumerate(ids, start=1):
        try:
            cambio, saltos = _aplicar_a_tarjeta(
                originales[card_id],
                nombres,
                por_nombre,
                sobrescribir,
                regenerar,
            )
        except ErrorProveedor as exc:
            errores.append(f"Tarjeta {card_id}: {exc}")
            progreso.progress(indice / len(ids))
            break
        except ErrorEnriquecimiento as exc:
            errores.append(f"Tarjeta {card_id}: {exc}")
            progreso.progress(indice / len(ids))
            continue
        except sqlite3.Error as exc:
            errores.append(f"Tarjeta {card_id}: no se pudo guardar ({exc})")
            progreso.progress(indice / len(ids))
            break
        if cambio:
            escritas += 1
        omitidas += saltos
        progreso.progress(indice / len(ids))
    partes = [f"Se escribieron {escritas} tarjeta(s)."]
    if omitidas:
        partes.append(f"Se omitieron {omitidas} campo(s).")
    if errores:
        partes.append(" ".join(errores))
    st.session_state["aviso_ia"] = " ".join(partes)
    st.session_state["editor_version"] += 1
    st.rerun()


def _aplicar_a_tarjeta(
    tarjeta: Card,
    nombres: tuple[str, ...],
    por_nombre: dict[str, Enriquecedor],
    sobrescribir: bool,
    regenerar: bool,
) -> tuple[bool, int]:
    """Devuelve si se guardó la tarjeta y cuántos campos se saltaron."""
    actual = tarjeta
    cambio = False
    saltos = 0
    for nombre in nombres:
        enriquecedor = por_nombre[nombre]
        campo = enriquecedor.campos[0]
        if campo != "subtitle" and getattr(actual, campo).strip() and not sobrescribir:
            saltos += 1
            continue
        resultado = enriquecedor.apply(actual, regenerar=regenerar)
        actual = resultado.tarjeta
        if resultado.cambio:
            cambio = True
        elif resultado.aviso:
            saltos += 1
    if not cambio or actual.id is None:
        return False, saltos
    subtitle = actual.subtitle if actual.subtitle != tarjeta.subtitle else None
    guardar_enriquecimiento(
        actual.id,
        actual.translation,
        actual.explanation,
        subtitle,
    )
    return True, saltos


def _ids_marcados(editado: pd.DataFrame, columna: str) -> list[int]:
    return [
        int(fila["id"])
        for _, fila in editado.iterrows()
        if bool(fila[columna]) and not _vacio(fila[columna])
    ]


def _generar_tsv() -> None:
    tarjetas = listar_tarjetas()
    if not tarjetas:
        st.warning("No hay tarjetas para exportar.")
        return
    nombre = datetime.now().strftime("tarjetas_%Y%m%d_%H%M%S.tsv")
    try:
        destino = exportar_tsv(tarjetas, EXPORT_DIR / nombre)
    except OSError as exc:
        st.error(f"No se pudo escribir el TSV: {exc}")
        return
    st.session_state["ultimo_tsv"] = str(destino)


def _texto(valor: object) -> str:
    """Convierte una celda del editor en texto, tratando vacíos como ''."""
    if _vacio(valor):
        return ""
    return str(valor)


def _vacio(valor: object) -> bool:
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
