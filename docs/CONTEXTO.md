# Reporte técnico Book2Anki

Fecha del reporte: 2026-10-07. Etapa documentada: 3 (modo estudio), más las etapas 1 y 2, la mini-etapa de borrados y la corrección de interfaz del mismo día.

## 1. Objetivo

Book2Anki es una herramienta personal, local, para convertir en tarjetas de Anki solo los párrafos que la persona elige de una nota de Obsidian o de un archivo `.md` / `.txt`. No procesa libros enteros. Importa el texto, lo parte en secciones y párrafos respetando las vallas de código, guarda la selección en SQLite, propone un resumen y tarjetas de estudio, propone traducción y explicación, y exporta un TSV. Audio, EPUB/PDF y `.apkg` quedan para después. `cards` ganó `code` y `code_lang` por `ALTER TABLE`. Se añadió `section_summaries`. `ai_cache` sigue igual.

## 2. Estado actual

Etapa 3 terminada, y el mismo día se corrigió la interfaz. El detalle está más abajo. Lo de las etapas 1 y 2 se conserva aquí.

Corrección de interfaz, el 2026-10-07, sobre una copia en `/tmp` con `BOOK2ANKI_DB`. `data/book2anki.db` siguió en 241664 bytes, con fecha 2026-10-07 18:49:59. No se escribió un TSV.

- Anterior y Siguiente escriben `seccion_sel` en `on_click`, antes de que el selectbox exista en esa pasada. En una fuente de una sola sección los dos botones quedan desactivados. En la primera, Anterior queda desactivado y Siguiente pasa a la siguiente (el selector de la barra cambia). Anterior vuelve. En la última, Siguiente queda desactivado.
- Con `BOOK2ANKI_PROVEEDOR=falso` no hay línea de RAM. Con `BOOK2ANKI_OLLAMA_MODELO=qwen2.5:7b` y Ollama apagado, Lectura muestra el aviso de 7B con los 8 GB de `RAM_GB`, y el fallo de conexión en español.
- En Mis tarjetas, `column_order` empieza por `borrar` y `generar`. `id` y `title` van con `pinned=True`. La tabla se pinta solo con esa pestaña abierta, para que el ancho se mida con la pestaña visible. Las dos casillas se ven sin desplazar. **Borrar seleccionadas** borró una tarjeta en la copia (de 4 a 3).
- pytest: `33 passed`.

Probado en el navegador, con `ejemplos/notas_ejemplo.md`:

- Arranque sin fuentes, importación por formulario, selectores de fuente y de sección.
- Seis secciones. La de nivel 4, «Nota al margen», muestra capítulo del `#`, título del `##` y subtítulo del `###`.
- «Añadir a tarjetas» guarda el párrafo, lo marca con «Ya en tarjetas» y desactiva ese botón. El otro párrafo de la misma sección sigue activo.
- La tarjeta queda con `lang` = `es`. Editar `title` y pulsar «Guardar cambios» persiste en SQLite.
- «Generar TSV» escribe `data/exportaciones/tarjetas_YYYYMMDD_HHMMSS.tsv` y muestra «Descargar TSV». El archivo en disco tenía las 12 columnas y el título editado.
- La casilla «Borrar» más «Borrar seleccionadas» deja la lista vacía y `cards` en 0.
- Una ruta inexistente muestra «No existe la ruta: …», sin traza.

Probado con un script de Python, no en el navegador:

- Partición del ejemplo, archivo sin encabezados, encabezado ATX cerrado (`## Título ##`).
- `detectar_idioma`: `es` en un párrafo largo; cadena vacía si hay menos de 20 caracteres.
- Alta, actualización y borrado de tarjeta. Un `original_text` corto deja `lang` vacío.
- TSV: saltos de línea a `<br>`, tabuladores internos a espacio, 12 columnas.
- Carpeta: entran `nota.md` y `sub/si.md`; se ignoran `.obsidian`, `.nota.md`, `sub/.secreto/` y los `.txt`.
- Ruta vacía y archivo inexistente.
- Un `.txt` en Latin-1 con «ñ» se lee bien.

Mini-etapa de borrados, el mismo día. El `CREATE TABLE` no cambió.

Probado en el navegador, otra vez con `ejemplos/notas_ejemplo.md`:

- Importar el archivo, añadir un párrafo y, en **Ajustes**, borrar todas las tarjetas. El aviso dijo «Se borraron 2 tarjetas.» La fuente siguió en el selector y el párrafo volvió a poder añadirse.
- Volver a importar la misma ruta mostró «Ya hay 1 fuente(s) con esta ruta y 0 tarjeta(s).» **Reemplazar** dejó una sola fuente con ese path (id nuevo) y cero tarjetas.
- **Borrar fuente seleccionada** quitó esa fuente del selector. El aviso dijo «Se borró 1 fuente, 6 secciones y 0 tarjetas.» No quedaron secciones huérfanas.
- **Restablecer todo**, sin marcar el borrado de exportaciones, vació las tres tablas. El aviso dijo «Se borraron 8 fuentes, 154 secciones y 0 tarjetas.» La barra lateral quedó en «Todavía no hay fuentes importadas.» El TSV de `data/exportaciones/` siguió en disco. `sqlite_sequence` quedó vacío, así que el siguiente id es 1.
- La base de trabajo se restauró después de esa prueba: 8 fuentes, 154 secciones y 1 tarjeta, como estaba antes de la mini-etapa.

Probado con un script contra una base temporal, no contra `data/book2anki.db`:

- Dos fuentes con secciones y tarjetas. `borrar_fuente` de una deja sus hijas en 0 y no toca la otra. El id siguiente no vuelve a 1.
- `borrar_todas_las_tarjetas` deja las fuentes.
- `restablecer_todo` deja las tres tablas vacías y el siguiente id de `sources` y de `cards` es 1.
- Planificar dos veces la misma ruta detecta la fuente. Reemplazar, también tras un «Añadir otra», deja una sola fuente y cero tarjetas viejas.
- En una carpeta, reemplazar añade el archivo nuevo y no borra una fuente cuyo archivo ya no está en la carpeta.
- Vaciar un directorio de exportación de prueba borra el TSV y el directorio.

No probado:

- Pulsar «Descargar TSV» en el navegador. Sí se leyó el archivo en disco.
- Editar en la tabla `subtitle`, `notes`, `tags` u `original_text`. En la interfaz solo se editó `title`. Esos campos sí se actualizaron por script.
- Importar una carpeta desde la interfaz. El reemplazo de carpeta sí se probó por script.
- Un archivo suelto que no sea `.md` ni `.txt`.
- La casilla «Borrar también los archivos de data/exportaciones/» en el navegador. El vaciado del directorio sí se probó por script, sobre un directorio temporal.
- Un campo del TSV con comillas dobles.
- Dos párrafos idénticos en la misma sección. El encabezado dentro de una valla quedó cubierto en la etapa 3.

## Etapa 2

La IA propone `translation` y `explanation`. La persona los edita en la tabla y luego exporta. Un modelo real no se probó: Ollama no estaba en marcha y no se instaló desde aquí.

Probado con pytest, base temporal, sin red (`11 passed`):

- JSON válido rellena `translation` solo si `lang` es `en`. Con `es` o `""` no se llama al proveedor.
- JSON inválido y luego válido: dos llamadas y el campo queda escrito.
- JSON inválido dos veces, o `generar` que lanza `ErrorProveedor`: la tarjeta sale igual y, en el primer caso, `ErrorEnriquecimiento`. La respuesta mala no entra en `ai_cache`.
- La segunda llamada igual sale de `ai_cache`. Con `regenerar=True` se vuelve a llamar y se sustituye el valor.
- Explicación con `lang` `es`. Subtítulo solo si está vacío.
- `exportar_tsv` incluye `translation` y `explanation`.
- Sin `BOOK2ANKI_API_KEY` no hay petición de red. Un nombre de proveedor distinto de `ollama` o `api` falla en español.

Probado en el navegador, con la tarjeta real en español (`lang` = `es`, id 1). Ollama en `http://127.0.0.1:11434` no respondía:

- **Probar conexión** mostró «Ollama no está en marcha en http://127.0.0.1:11434. Arráncalo con ollama serve.» Sin traza. Proveedor `ollama`, modelo `qwen2.5:3b`.
- **Generar traducción** sobre esa tarjeta: «Se escribieron 0 tarjeta(s). Se omitieron 1 campo(s).» No se llamó al modelo.
- **Generar explicación**: «Se escribieron 0 tarjeta(s). Tarjeta 1: Ollama no está en marcha en http://127.0.0.1:11434. Arráncalo con ollama serve.» La tarjeta no se escribió.
- Editar a mano `translation` y `explanation`, **Guardar cambios** y **Generar TSV**. El archivo `data/exportaciones/tarjetas_20261007_172753.tsv` tiene las 12 columnas y esos dos campos rellenos. El TSV anterior, `tarjetas_20261007_155503.tsv`, sigue en disco.
- Después de leer ese archivo, `translation` y `explanation` de la tarjeta se dejaron otra vez vacíos. El TSV de la prueba se conservó.

No probado con un modelo en marcha: generar de verdad, el reintento de JSON contra Ollama, la caché en la interfaz y el proveedor `api`.

## Etapa 3

Modo estudio. `resumir_seccion` propone un resumen en español y de 1 a 3 tarjetas. Nada entra en `cards` hasta **Guardar tarjeta** o **Guardar todas**. El resumen editado va a `section_summaries`. El resumidor no implementa `Enriquecedor`: ese protocolo entra y sale con una `Card`.

Probado con pytest, base temporal, sin red (`30 passed`, incluidas las 11 de la etapa 2):

- Un `# comando ls` dentro de ` ```bash ` sigue en el cuerpo y el bloque, con su línea en blanco, es un solo párrafo. Una valla sin cerrar llega hasta el final del archivo y no lanza. `~~~python` también es un párrafo.
- Una base creada con el `CREATE` viejo, sin `code`, conserva la fila tras `inicializar()`. Aparecen `code`, `code_lang` (vacíos) y `section_summaries`. `restablecer_todo` borra el resumen y no toca `ai_cache`. `BOOK2ANKI_DB` cambia `config.DB_PATH`.
- El TSV tiene 14 columnas. `code` sale como `<pre><code class="language-bash">…<br>…</code></pre>`, en una sola fila de datos. Un `<` del código sale como `&lt;`.
- `sugerir_tarjetas`: menos de 150 palabras, 1; de 150 a 400, 2; más de 400, 3.
- JSON con 1, 2 y 3 tarjetas. Si `code` no aparece tal cual en la sección, se vacían `code` y `code_lang` y hay un aviso; la tarjeta se queda. El código literal se conserva.
- JSON inválido y luego válido: dos llamadas. Dos inválidos: `ErrorEnriquecimiento` y `ai_cache` vacía. La segunda llamada igual sale de la caché. `regenerar=True` vuelve a llamar.
- Con `lang == "en"` se conserva `translation`. Con otro idioma queda vacía.
- Un texto de más de 3500 caracteres hace más de una llamada y el código del trozo se conserva.
- `proveedor_desde_config("falso").probar()` dice que no usa la red.

Probado en el navegador el 2026-10-07, en `http://127.0.0.1:8502`, con `BOOK2ANKI_DB` en una copia bajo `/tmp` y `BOOK2ANKI_PROVEEDOR=falso`. Ollama no respondía y no se instaló. `data/book2anki.db` siguió en 237568 bytes, con fecha 2026-10-07 17:28:23. No se escribió un TSV nuevo en `data/exportaciones/`.

- Importar `ejemplos/con_codigo.md` dejó una sección, «Listar archivos». El bloque bash se pintó como código. Anterior y Siguiente quedaron desactivados, porque no hay otra sección.
- El panel derecho mostró «falso · falso», «Proveedor de prueba: no usa la red.» y «tu RAM es de 8 GB». Sin traza.
- Con el número de tarjetas en 2, **Generar resumen y tarjetas** mostró dos propuestas. La primera traía `# comando ls`, `ls -l` y lenguaje `bash`.
- El resumen se editó a «Resumen editado a mano.» y **Guardar resumen** lo dejó en `section_summaries`.
- **Guardar tarjeta** guardó la primera. **Descartar** quitó la segunda. En la copia quedó una sola fila: título «Tarjeta 1», `code` con ese bash y `code_lang` = `bash`.
- En **Mis tarjetas**, `code` y `code_lang` son columnas editables. La celda de código muestra el bloque y `code_lang` muestra `bash`.

El aviso de 7B se comprobó después, en la corrección de interfaz, con `qwen2.5:7b` y Ollama apagado.

## Resumen con qwen2.5:3b

Probado el 2026-10-07 con Ollama en marcha y `qwen2.5:3b` (1.9 GB, Q4_K_M). La base de trabajo no se abrió en escritura: `data/book2anki.db` siguió en 241664 bytes, fecha 2026-10-07 22:26:58. Las llamadas usaron una copia en `/tmp`.

Antes de cambiar el prompt, la sección «¿Qué significa grep?» (3381 caracteres, una valla `sh`) pidió el JSON grande. La primera respuesta tardó 72 s, `done_reason` fue `stop`, `prompt_eval_count` 1125 y `eval_count` 383. El JSON era válido y traía tres tarjetas, pero no traía `resumen`. La segunda llamada, 47 s, repitió el mismo hueco. El mensaje de la interfaz no decía la causa y la terminal no escribía nada. El código no enviaba `num_ctx`, `num_predict` ni `temperature`. El modelo anuncia 32768 de contexto; 1125 tokens caben también en 2048. El prompt no se cortó por el contexto.

Con las llamadas separadas y las opciones explícitas, un script obtuvo el resumen en 64 s. En el navegador, en el puerto 8507, **Generar resumen y tarjetas** con 3 tarjetas tardó 265 s. El resumen explica `grep` y las opciones `-i`, `-c` y `-m`. Una tarjeta se quedó con el `wget` de la valla; las otras dos citan la introducción y dejan `code` vacío. La primera pasada del navegador, sin `repeat_penalty`, abortó con «prediction aborted, token repeat limit reached».

Con el proveedor falso, pytest cubre la valla ` ```json `, el texto alrededor, la coma final, el JSON cortado, los campos que faltan y una llamada por tarjeta. Eso no usa la red.

## 3. Árbol

Código del proyecto. `.venv/` y `data/` existen en local, están en `.gitignore` y no forman parte del diseño.

```text
book2anki/
  app.py
  config.py
  models.py
  providers.py
  enriquecedores.py
  registro.py
  db.py
  importers.py
  exporter.py
  tests/test_enriquecedores.py
  tests/test_importador.py
  tests/test_esquema.py
  tests/conftest.py
  tests/test_navegacion.py
  tests/test_resumen.py
  requirements.txt
  README.md
  .gitignore
  .streamlit/config.toml
  ejemplos/notas_ejemplo.md
  ejemplos/con_codigo.md
  docs/CONTEXTO.md
```

`data/book2anki.db`, `data/exportaciones/` y `data/logs/ia.log` se crean al usar la app. El log no entra en git.

## 4. Esquema SQLite

El esquema que queda tras `inicializar()` en [db.py](../db.py). El `CREATE` de `cards` no incluye `code` ni `code_lang`: se añaden después. Cada conexión ejecuta `PRAGMA foreign_keys = ON`.

```sql
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL
        REFERENCES sources(id) ON DELETE CASCADE,
    heading TEXT NOT NULL,
    level INTEGER NOT NULL,
    position INTEGER NOT NULL,
    chapter TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    subtitle TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL
        REFERENCES sources(id) ON DELETE CASCADE,
    section_id INTEGER NOT NULL
        REFERENCES sections(id) ON DELETE CASCADE,
    chapter TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    subtitle TEXT NOT NULL DEFAULT '',
    lang TEXT NOT NULL DEFAULT '',
    original_text TEXT NOT NULL,
    audio TEXT NOT NULL DEFAULT '',
    translation TEXT NOT NULL DEFAULT '',
    explanation TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    code_lang TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sections_source
    ON sections(source_id, position);
CREATE INDEX IF NOT EXISTS idx_cards_section
    ON cards(section_id);

CREATE TABLE IF NOT EXISTS section_summaries (
    section_id INTEGER PRIMARY KEY
        REFERENCES sections(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_cache (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

`code` y `code_lang` no están en el `CREATE` original: `inicializar()` las añade con `ALTER TABLE` si faltan, sin borrar filas. `section_summaries` se crea con `CREATE TABLE IF NOT EXISTS`. `restablecer_todo` hace `DELETE` de esa tabla y, además, la cascada al borrar secciones. No borra `ai_cache`.

`clave` es el SHA-256 de proveedor, modelo, prompt y texto. Solo se guarda JSON ya validado. `regenerar=True` no lee la caché y la sustituye.

`kind` vale `archivo` o `obsidian`. `created_at` e `imported_at` son ISO 8601 UTC, sin microsegundos. `source_name` no es columna: sale del `JOIN` con `sources.name` al listar tarjetas.

## 5. Módulos

Los módulos viven en la raíz, sin paquete. `streamlit run app.py` debe lanzarse desde esa raíz.

[config.py](../config.py). Rutas y parámetros del modelo, leídos del entorno. No tiene funciones.

- `RAIZ`, `DATA_DIR`, `DB_PATH`, `EXPORT_DIR` (`data/exportaciones`), `SIN_TITULO` = `(sin título)`.
- `DB_PATH` es `BOOK2ANKI_DB` si esa variable tiene texto; si no, `data/book2anki.db`.
- `RAM_GB` (`BOOK2ANKI_RAM_GB`, defecto 8). Lectura lo usa solo en el aviso, cuando el nombre del modelo trae un tamaño `7b` o mayor.
- `PROVEEDOR` (`BOOK2ANKI_PROVEEDOR`, defecto `ollama`), `OLLAMA_URL`, `OLLAMA_MODELO` (defecto `qwen2.5:3b`). El valor `falso` no sale en el selector: lo usa el arranque de prueba.
- `API_URL`, `API_MODELO`, `API_KEY` (`BOOK2ANKI_API_URL`, `BOOK2ANKI_API_MODEL`, `BOOK2ANKI_API_KEY`). La clave no se guarda en código ni en la base.
- `LLM_TIMEOUT` (`BOOK2ANKI_LLM_TIMEOUT`, defecto 120 segundos).

[models.py](../models.py). Datos y el protocolo de enriquecedores.

- `Source(id, name, path, kind, imported_at)`: un archivo importado.
- `Section(heading, level, position, chapter, title, subtitle, body, id=None, source_id=None)`: trozo entre encabezados.
- `Card(...)`: tarjeta elegida a mano. `code` y `code_lang` van después de `explanation`, por defecto `""`. `audio` sigue vacío.
- `ResultadoEnriquecimiento(tarjeta, cambio, aviso)`: la tarjeta (la de entrada si no hubo cambio), si cambió y un aviso en español.
- `ErrorEnriquecimiento`: el JSON no valió tras el reintento. La tarjeta no se modifica.
- `Enriquecedor`: `name: str`, `campos: tuple[str, ...]`, `apply(self, card: Card, *, regenerar: bool = False) -> ResultadoEnriquecimiento`.
- `ENRIQUECEDORES: list[Enriquecedor] = []`. La rellena `usar_proveedor`.

[providers.py](../providers.py). Texto. Los errores son `ErrorProveedor`, en español y sin traza.

- `LLMProvider.generar(self, system: str, prompt: str) -> str` y `probar(self) -> str`.
- `OllamaProvider`: `POST {url}/api/chat` con `stream: false`, `format: json` y `options` (`num_ctx` 4096, `temperature` 0.2, `num_predict` 512 en el resumen y 768 en cada tarjeta, `repeat_penalty` 1.1). URL por defecto `http://127.0.0.1:11434`. Cada llamada se anota en `data/logs/ia.log` mediante [registro.py](../registro.py): proveedor, modelo, caracteres del prompt, segundos y cuerpo crudo. Sin claves.
- `ApiProvider`: `POST {url}/chat/completions`. Si falta la clave, el mensaje lo dice y no hay petición.
- `FalsoProvider`: sin red. `probar` dice que es de prueba. `generar` arma una tarjeta si el prompt pide `title`, un resumen si pide `resumen`, y un campo suelto en el resto. El código de la valla no lo inventa: lo copia el texto de la tarjeta.
- `proveedor_desde_config(nombre: str | None = None, modelo: str | None = None) -> LLMProvider`. `falso` se resuelve antes que `ollama` y `api`. Un nombre distinto de esos tres falla en español.

[enriquecedores.py](../enriquecedores.py). El modelo responde solo JSON. Si no valida, un segundo `generar` pide JSON de nuevo. Si también falla, `ErrorEnriquecimiento`.

- `Traductor`: campo `translation`. Solo si `lang == "en"`.
- `Explicador`: campo `explanation`, resumen en español de 2 o 3 frases, cualquier idioma.
- `Subtitulador`: campo `subtitle`, solo si está vacío. Entra en «Generar todo» y no tiene botón propio.
- `usar_proveedor(proveedor: LLMProvider) -> None`: deja esos tres en `ENRIQUECEDORES`.
- `TarjetaPropuesta(title, subtitle, original_text, explanation, code, code_lang, translation="")`.
- `ResultadoResumen(resumen, tarjetas, avisos)`.
- `sugerir_tarjetas(texto: str) -> int`: 1, 2 o 3 según el número de palabras.
- `resumir_seccion(proveedor, texto, *, n, lang, regenerar=False) -> ResultadoResumen`. Pide exactamente `n` (entre 1 y 3) en llamadas separadas: primero `{"resumen"}` y luego una tarjeta `{"title","subtitle","original_text","explanation"}`. Si `lang == "en"`, esa tarjeta pide también `translation`. Si el texto pasa de 3500 caracteres, antes resume por párrafos sin partir una valla. El código no lo escribe el modelo: `_asignar_codigo` copia cada valla a la tarjeta cuyo texto la contiene. Si ninguna la contiene, hay un aviso. `_cargar_json` quita ` ```json `, recorta del primer `{` al último `}` y quita una coma final antes de reintentar. La caché sigue por prompt. El segundo fallo es `ErrorEnriquecimiento` y nombra la causa (cortado, no es JSON, faltan campos) y `data/logs/ia.log`. `ErrorProveedor` sube, también el tiempo agotado y la salida repetida.

[db.py](../db.py). SQLite.

- `conectar() -> sqlite3.Connection`: abre la base, crea `data/` y activa claves foráneas.
- `inicializar() -> None`: crea tablas e índices si no existen.
- `guardar_fuente(name: str, path: str, kind: str, secciones: list[Section]) -> int`: inserta fuente y secciones.
- `listar_fuentes() -> list[Source]`: de la más reciente a la más antigua.
- `listar_secciones(source_id: int) -> list[Section]`: en orden de lectura.
- `obtener_seccion(section_id: int) -> Section | None`.
- `crear_tarjeta(tarjeta: Card) -> int`.
- `listar_tarjetas() -> list[Card]`: incluye `source_name`.
- `textos_de_seccion(section_id: int) -> set[str]`: textos ya convertidos en tarjeta, recortados.
- `guardar_enriquecimiento(card_id, translation, explanation, subtitle: str | None = None) -> None`: si `subtitle` es `None`, no lo toca.
- `leer_cache(clave: str) -> str | None` y `guardar_cache(clave: str, valor: str) -> None`.
- `guardar_resumen(section_id: int, summary: str) -> None` y `leer_resumen(section_id: int) -> str | None`.
- `actualizar_tarjeta(card_id, title, subtitle, notes, tags, original_text, lang, code, code_lang) -> None`: todos `str` salvo el id. `code` y `code_lang` son obligatorios para no borrar el código si alguien olvida el argumento.
- `borrar_tarjetas(ids: list[int]) -> None`.
- `contar_tarjetas_de(source_ids: list[int]) -> int`.
- `fuentes_con_rutas(paths: list[str]) -> list[Source]`: fuentes cuyo `path` absoluto coincide.
- `borrar_todas_las_tarjetas() -> int`: borra `cards` y devuelve cuántas había.
- `borrar_fuente(source_id: int) -> tuple[int, int]`: solo `DELETE FROM sources`. Devuelve `(secciones, tarjetas)`. Si quedan hijas, lanza `RuntimeError`.
- `restablecer_todo() -> tuple[int, int, int]`: vacía `section_summaries`, `cards`, `sections` y `sources`, borra las filas de `sqlite_sequence` de las tres tablas originales y devuelve `(fuentes, secciones, tarjetas)`. No toca `ai_cache`.

[importers.py](../importers.py). Lectura, partición e idioma. Llama a `guardar_fuente`.

- `ErrorImportacion(Exception)`: mensaje para la interfaz.
- `detectar_idioma(texto: str) -> str`: código de idioma, o `""` si no es fiable.
- `leer_texto(ruta: Path) -> str`: UTF-8 con BOM y, si falla, Latin-1.
- `partir_parrafos(cuerpo: str) -> list[str]`: bloques separados por línea en blanco. Una valla cerrada (` ``` ` o `~~~`, tres o más, mismo carácter al cerrar, hasta 3 espacios de sangría) es un solo párrafo, con sus líneas en blanco y la marca de lenguaje.
- `codigo_de_parrafo(parrafo: str) -> tuple[str, str] | None`: `(lenguaje, interior)` si el párrafo es una valla cerrada.
- `texto_sin_vallas(texto: str) -> str`: prosa sin las vallas, para detectar el idioma.
- `partir_secciones(texto: str) -> list[Section]`: corta por encabezados ATX. Dentro de una valla no hay encabezados. Una valla abierta abarca hasta el final del archivo.
- `planificar_importacion(ruta: str) -> list[tuple[Path, str, str]]`: valida y devuelve `(ruta absoluta, kind, nombre)` sin escribir.
- `importar_plan(entradas: list[tuple[Path, str, str]]) -> list[int]`: inserta un plan ya resuelto.
- `importar_ruta(ruta: str) -> list[int]`: planifica y luego inserta.
- `listar_markdown(carpeta: Path) -> list[Path]`: `.md` visibles, sin entrar en directorios ocultos.

[exporter.py](../exporter.py). TSV. No consulta la base.

- `COLUMNAS`: las 12 de antes y, al final, `code` y `code_lang`.
- `html_codigo(codigo: str, lenguaje: str) -> str`: vacío si no hay código. Si lo hay, `html.escape`, saltos a `<br>` y envoltura `<pre><code class="language-…">`. La clase solo entra si el lenguaje es `[A-Za-z0-9_+-]+`.
- `celda(valor: object) -> str`: saltos a `<br>`, tabuladores a espacio.
- `filas_tsv(tarjetas: list[Card]) -> list[list[str]]`: filas ya escapadas, sin cabecera.
- `exportar_tsv(tarjetas: list[Card], destino: Path) -> Path`: escribe UTF-8.

[app.py](../app.py). Interfaz Streamlit. Pestañas Lectura, Mis tarjetas, Exportar y Ajustes.

- `main() -> None`: arranque.
- `barra_lateral() -> tuple[int | None, int | None]`: importar y elegir fuente y sección. Si el path ya existe, pregunta **Reemplazar** o **Añadir otra**.
- `id_vecino(ids: list[int], actual: int, paso: int) -> int | None`: id anterior (`paso` -1) o siguiente (`paso` 1). `None` en el extremo o si el id no está.
- `pintar_lectura(seccion_id: int | None) -> None`: dos columnas. Cada una es un contenedor de alto fijo con scroll propio. A la izquierda, anterior/siguiente (el `on_click` fija `seccion_sel` antes de pintar el selectbox), el cuerpo (vallas con `st.code`) y **Añadir a tarjetas**. A la derecha, el modelo, el resumen y las propuestas. El aviso de RAM solo entra si `_modelo_grande` reconoce un `7b` o mayor.
- `pintar_tarjetas() -> None`: tabla editable, generación y borrado. Se pinta cuando la pestaña está abierta. `column_order` empieza por `borrar` y `generar`; `id` y `title` van fijadas. Columnas editables: `title`, `subtitle`, `notes`, `tags`, `original_text`, `translation`, `explanation`, `code` y `code_lang`. La casilla `generar` no se guarda.
- `pintar_ajustes(fuente_id: int | None) -> None`: proveedor, modelo, «Probar conexión» y los borrados. La elección queda en `st.session_state` y no reescribe `config.py`.
- `pintar_exportar() -> None`.

Internas de `app.py`, por si hay que tocar el flujo: `_preparar_importacion`, `_pintar_decision_reimportar`, `_ejecutar_importacion`, `_pintar_borrar_tarjetas`, `_pintar_borrar_fuente`, `_pintar_restablecer`, `_vaciar_exportaciones`, `_avisar_ajustes`, `_elegir_seccion`, `_pintar_navegacion`, `_pintar_cuerpo`, `_pintar_estudio`, `_pintar_estado_modelo`, `_modelo_grande`, `_generar_resumen`, `_guardar_resumen_editado`, `_pintar_propuesta`, `_guardar_propuesta`, `_proveedor_activo`, `_crear_desde_parrafo(seccion, parrafo) -> bool`, `_tabla_tarjetas`, `_guardar_edicion`, `_borrar_marcadas`, `_pintar_modelo`, `_generar`, `_aplicar_a_tarjeta`, `_ids_marcados`, `_generar_tsv`, `_texto`, `_vacio`.

Las propuestas viven en `st.session_state` bajo la `section_id`. Generar vuelca el resultado antes de pintar los widgets. Editar un campo no borra la propuesta. Un fallo de conexión se muestra en español y no escribe nada. Si el párrafo es una valla cerrada, **Añadir a tarjetas** guarda el bloque entero en `original_text` y el interior en `code`. Si `BOOK2ANKI_PROVEEDOR` es `falso`, Lectura usa ese proveedor aunque el selector diga `ollama`.

`_generar` recorre las filas con la casilla **Generar**. Si no hay ninguna, avisa y no llama al modelo. Un fallo de conexión detiene el lote. Un JSON malo en una tarjeta no impide seguir con la siguiente, y esa tarjeta no se escribe. Sin «Sobrescribir las que ya tienen texto», un campo relleno se omite.

[.streamlit/config.toml](../.streamlit/config.toml). `server.address = 127.0.0.1` y `browser.gatherUsageStats = false`. `streamlit run app.py` desde la raíz lo toma solo.

## 6. Decisiones

- Una fuente es un archivo. Una carpeta crea una fuente por cada `.md`, con la ruta relativa como nombre. Así el selector no mezcla cientos de secciones de un almacén en una sola lista.
- `chapter` / `title` / `subtitle` salen de `#` / `##` / `###` y se copian a la tarjeta al crearla. Un nivel 4 o mayor solo cambia `heading`; hereda el contexto de los niveles 1 a 3.
- El texto anterior al primer encabezado, o un archivo sin encabezados, es la sección `(sin título)`.
- Una sección cuyo cuerpo queda vacío no se guarda. Si el archivo no produce ninguna sección con cuerpo, se guarda una sola `(sin título)` con el texto completo.
- Los párrafos son bloques separados por una línea en blanco. Una valla cerrada no se parte, aunque tenga líneas en blanco. «Ya añadido» compara el texto recortado dentro de esa `section_id`, y en una valla ese texto es el bloque entero.
- El resumidor es una función, no un `Enriquecedor`. La propuesta se queda en la sesión hasta que la persona guarda. El recuento inicial sale de `sugerir_tarjetas` y se puede cambiar entre 1 y 3.
- En el TSV, un salto real partiría la fila. `code` lleva `<br>` dentro de `<pre><code>`, que Anki pinta en monoespacio. Si `code` está vacío, la celda queda vacía.
- La ruta y el botón de importar van en un `st.form`. Streamlit no confirma un `text_input` hasta que pierde el foco; sin formulario, pulsar el botón enviaba la ruta vacía. Comprobado en el navegador.
- Si el path absoluto ya está en `sources`, la interfaz no escribe hasta que se elige. **Reemplazar** borra cada fuente con ese path (también un duplicado previo) y vuelve a importar. **Añadir otra** inserta sin borrar. En una carpeta, el reemplazo no toca una fuente cuyo archivo ya no está en la carpeta.
- `borrar_fuente` solo ejecuta `DELETE FROM sources`. Las hijas caen por `ON DELETE CASCADE` porque `conectar()` activa las claves foráneas. Si quedara alguna, la transacción falla con `RuntimeError` y no se confirma.
- **Restablecer todo** borra `cards`, `sections` y `sources`, y las filas de `sqlite_sequence` de esas tablas, para que el siguiente id sea 1. No borra el archivo `book2anki.db`. La casilla de exportaciones, desmarcada al empezar, borra los archivos de `EXPORT_DIR`.
- `audio` sigue vacío. `translation` y `explanation` los propone un enriquecedor o los escribe la persona. El TSV ya los incluye.
- `apply` devuelve `ResultadoEnriquecimiento` porque un `Card` solo no puede decir «no hice nada» ni «el servicio falló». `ErrorProveedor` sube y la interfaz corta el lote. `ErrorEnriquecimiento` se cuenta y se sigue con la tarjeta siguiente.
- La caché guarda el JSON validado bajo la clave del prompt original. El reintento usa otro prompt, pero el acierto se guarda con la clave primera. Una respuesta inválida no se cachea.
- Idioma con `langdetect`, semilla fija, mínimo 20 caracteres y probabilidad 0.8. Por debajo, `lang` queda vacío y la app sigue.
- Codificación: UTF-8 con BOM y, si falla, Latin-1. Los errores de ruta se muestran en español, sin traza.
- El TSV usa `csv` con tabulador y `QUOTE_MINIMAL`, después de sustituir saltos y tabuladores. Así Anki no parte una fila por un salto interno.
- Nombres de tablas y columnas en inglés, como el futuro mazo de Anki. Funciones, interfaz y comentarios en español.

## 7. Puntos de extensión

- El audio puede ser otro `Enriquecedor` con `campos = ("audio",)`, registrado junto a los tres de texto.
- Columna vacía de `cards`: `audio`.
- `importar_ruta` ya distingue archivo y carpeta. Un importador EPUB o PDF puede producir `list[Section]` y llamar a `guardar_fuente` con otro `kind`.
- `exportar_tsv` ya escribe las columnas que usará un `.apkg`. No depende de cómo se rellenaron.

## 8. Dependencias y comandos

Entorno comprobado: Debian 12, Python 3.11.2.

[requirements.txt](../requirements.txt) declara `streamlit>=1.32`, `langdetect>=1.0.9`, `requests>=2.31` y `pytest>=8`. En `.venv`, el 2026-10-07, quedaron instalados `streamlit` 1.65.0 y `langdetect` 1.0.9. `pandas` 3.0.6 entra solo porque Streamlit lo exige; no está en `requirements.txt`. La interfaz lo usa para `st.data_editor`.

```bash
.venv/bin/python -m pytest tests -q
```

El 2026-10-07: `30 passed`. Ninguna prueba escribe en `data/book2anki.db`.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /home/ale/Documents/projects/book2anki
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

El entorno virtual del proyecto ya existe. Para repetir la prueba: `ejemplos/notas_ejemplo.md`.

## 9. Limitaciones y deuda

- Pytest cubre enriquecedores, vallas, migración, TSV de código y el resumidor, con proveedor falso y base temporal. La importación de carpetas, los borrados y el resto de la interfaz siguen en verificación manual.
- Dos párrafos iguales en la misma sección se marcan los dos al guardar uno.
- Si se edita `original_text`, el párrafo original deja de verse como añadido. El idioma solo se recalcula si ese campo cambió.
- Solo encabezados ATX de `#` a `######`. No hay setext. Las vallas ` ``` ` y `~~~` sí se respetan.
- `tags` es texto libre, no una tabla.
- La tabla de tarjetas sigue siendo ancha. Borrar y Generar van las primeras y se ven sin desplazar; `id` y `title` se quedan fijas. El resto de las columnas se desplaza. Con una fila, el alto visible es el de la cabecera más esa fila. La tabla se monta al abrir la pestaña: si se pintara oculta, Streamlit mediría un ancho de unas decenas de píxeles y la rejilla no se vería.
- El TSV con comillas dentro de un campo no se probó. `csv` las duplicaría y entrecomillaría el campo.
- Con `qwen2.5:3b` en CPU y 8 GB, tres tarjetas tardaron 265 s. El resumen sirve; alguna tarjeta cita solo la introducción y deja `code` vacío si no copia el comando. El log de esa pasada está en `data/logs/ia.log`.
- No hay búsqueda, filtro, audio ni exportación `.apkg`.

## 10. Convenciones

- Interfaz, comentarios, docstrings y errores de uso: español.
- Tablas, columnas y los dataclasses `Source`, `Section`, `Card`: inglés.
- Funciones públicas en español, con type hints y docstring de una línea.
- Lo interno lleva prefijo `_`.
- Errores esperables suben como `ErrorImportacion` o se muestran con `st.error` / `st.sidebar.error`. No se traga `sqlite3.Error`.
- Una etapa nueva no rellena a mano `translation`, `explanation` o `audio` saltándose `Enriquecedor`, salvo una migración explícita.
- Al cerrar cada etapa se actualizan README.md (funciones, requisitos, variables, registro de cambios) y docs/CONTEXTO.md.

## 11. Próxima etapa

Audio, enchufado al mismo protocolo. EPUB/PDF y `.apkg` van después.

1. Un enriquecedor con `campos = ("audio",)` que llame a Piper o a edge-tts y escriba la ruta en `audio`.
2. Guardar el archivo bajo `data/` y persistirlo sin cambiar el `CREATE TABLE` de `cards`. [exporter.py](../exporter.py) ya tiene la columna.
3. En «Mis tarjetas», un botón sobre las filas marcadas. Si el servicio no responde, la tarjeta no se modifica y el aviso va en español, sin traza.
4. Probar en el navegador una tarjeta real y el TSV con `audio` relleno.
5. Al cerrar la etapa, actualizar README.md (funciones, requisitos, variables, registro de cambios) y este archivo: qué quedó probado y cuál es la etapa de después.
