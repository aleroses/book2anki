# Book2Anki

## 1. Qué es

Book2Anki es una herramienta personal y local. Sirve para convertir en tarjetas de Anki solo los párrafos que tú eliges de una nota de Obsidian o de un archivo `.md` o `.txt`. Importa el texto, lo parte en secciones y párrafos (un bloque de código cerrado no se parte), lo guarda en SQLite, puede proponer un resumen y tarjetas de estudio, puede proponer traducción y explicación, y exporta un TSV listo para importar en Anki de escritorio.

## 2. Qué hace

El flujo es: importar, leer, resumir o proponer tarjetas, editar, guardar y exportar.

La barra lateral pide una ruta, importa el archivo o la carpeta y deja elegir la fuente y la sección. Si esa ruta ya estaba importada, pregunta si quieres reemplazarla o añadir otra. En una carpeta se leen los `.md` y se ignoran las carpetas ocultas, como `.obsidian`.

**Lectura.** Dos columnas. A la izquierda, el texto de la sección, con **Anterior** y **Siguiente**. En la primera sección Anterior queda desactivado; en la última, Siguiente. Cada párrafo tiene **Añadir a tarjetas**. Si el párrafo es un bloque de código cerrado, la tarjeta guarda el bloque en el texto y el interior en `code`. A la derecha están el modelo, el resumen y las tarjetas propuestas. **Generar resumen y tarjetas** pide primero un resumen y después una tarjeta por llamada. El código no lo escribe el modelo: sale de las vallas de la sección y se asigna a la tarjeta cuyo texto lo contiene. Nada entra en la base hasta **Guardar resumen**, **Guardar tarjeta** o **Guardar todas**.

**Mis tarjetas.** Tabla de lo ya guardado. Puedes editar `title`, `subtitle`, `notes`, `tags`, `original_text`, `translation`, `explanation`, `code` y `code_lang`, y pulsar **Guardar cambios**. Las casillas **Borrar** y **Generar** se ven sin desplazar la tabla. `id` y `title` se quedan fijas al mover el resto. **Borrar seleccionadas** elimina las filas marcadas. **Generar traducción**, **Generar explicación** y **Generar todo** rellenan los campos de las filas marcadas en Generar. Un campo que ya tiene texto se conserva, salvo que marques **Sobrescribir las que ya tienen texto**.

**Exportar.** **Generar TSV** escribe un archivo UTF-8 en `data/exportaciones/`. Los saltos de línea pasan a `<br>` y los tabuladores internos a espacios. **Descargar TSV** ofrece ese archivo.

**Ajustes.** Eliges proveedor (`ollama` o `api`) y modelo, y **Probar conexión** dice si responde. La elección se queda en la página y no reescribe `config.py`. También puedes borrar todas las tarjetas, borrar la fuente seleccionada o restablecer la base. Cada borrado pide confirmación.

## 3. Qué queda para después

El audio, la importación de EPUB y PDF, y el mazo `.apkg` están previstos y todavía no existen. El campo `audio` viaja vacío en el TSV. Tampoco hay búsqueda ni filtro de tarjetas.

## 4. Requisitos

- Debian 12 o un derivado, con `python3`, `python3-venv` y `python3-pip`.
- Python 3.11 o superior. En esta máquina: Python 3.11.2.
- Las librerías de `requirements.txt`: Streamlit, `langdetect`, `requests` y pytest. Aquí Streamlit es 1.65.0. Esa versión permite fijar las columnas `id` y `title`.
- RAM orientativa: 8 GB con `qwen2.5:3b` y 16 GB con `qwen2.5:7b`. El aviso de la página usa `BOOK2ANKI_RAM_GB` (defecto 8) cuando el nombre del modelo es de 7B o más.
- Disco para el modelo de Ollama. `qwen2.5:3b` ocupa 1.9 GB según `/api/tags` (1929912432 bytes, cuantización Q4_K_M). El tamaño de `qwen2.5:7b` no se midió.
- Ollama, si el proveedor es `ollama`. Con el proveedor `api` hace falta la URL, el modelo y la clave en el entorno, y Ollama no.
- Anki de escritorio, para importar el TSV. Esa importación no se hizo en esta máquina.

## 5. Instalación

En otra máquina, copia la carpeta del proyecto y, desde su raíz:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /ruta/al/proyecto/book2anki
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En esta máquina la raíz es `/home/ale/Documents/projects/book2anki`. El entorno virtual ya existe.

Si vas a usar Ollama (no se instaló en esta pasada):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull qwen2.5:3b
```

Arranque, con el entorno activado y desde la raíz:

```bash
streamlit run app.py
```

La página queda en `http://127.0.0.1:8501`. Streamlit escucha solo en `127.0.0.1`.

Para comprobarlo:

```bash
python3 --version
.venv/bin/python -m pytest tests -q
curl -sS -m 5 http://127.0.0.1:11434/api/tags
```

El 2026-10-07, `python3 --version` dio Python 3.11.2 y pytest dio `39 passed`. Más tarde, el mismo día, `curl` a `http://127.0.0.1:11434/api/tags` respondió y listó `qwen2.5:3b`. Con Ollama apagado, **Probar conexión** muestra «Ollama no está en marcha en http://127.0.0.1:11434. Arráncalo con ollama serve.»

Una prueba de la interfaz sin red: `BOOK2ANKI_PROVEEDOR=falso streamlit run app.py`. Ese valor no sale en el selector. Para no tocar la base de trabajo, apunta `BOOK2ANKI_DB` a una copia.

Para probar el importador, con la app arrancada desde la raíz, importa `ejemplos/notas_ejemplo.md` o `ejemplos/con_codigo.md`.

## 6. Variables de entorno

La clave de la API solo se lee del entorno. No va en el código ni en la base.

| Variable | Qué hace | Defecto |
| --- | --- | --- |
| `BOOK2ANKI_DB` | Ruta del archivo SQLite | `data/book2anki.db` |
| `BOOK2ANKI_RAM_GB` | Cifra de RAM que usa el aviso de modelos grandes | `8` |
| `BOOK2ANKI_PROVEEDOR` | `ollama` o `api`. `falso` es solo para pruebas y no sale en el selector | `ollama` |
| `BOOK2ANKI_OLLAMA_URL` | Dirección de Ollama | `http://127.0.0.1:11434` |
| `BOOK2ANKI_OLLAMA_MODELO` | Modelo local | `qwen2.5:3b` |
| `BOOK2ANKI_API_URL` | Base de una API compatible con OpenAI | vacío |
| `BOOK2ANKI_API_MODEL` | Modelo de esa API | vacío |
| `BOOK2ANKI_API_KEY` | Clave de esa API | vacío |
| `BOOK2ANKI_LLM_TIMEOUT` | Segundos de espera de una generación | `120` |

Ejemplo con API, en la misma terminal donde arrancas Streamlit:

```bash
export BOOK2ANKI_PROVEEDOR=api
export BOOK2ANKI_API_URL=https://ejemplo.invalid/v1
export BOOK2ANKI_API_MODEL=nombre-del-modelo
export BOOK2ANKI_API_KEY=la-clave
streamlit run app.py
```

`data/exportaciones/` no cambia aunque `BOOK2ANKI_DB` apunte a otra base. El TSV sigue saliendo en esa carpeta.

## 7. Carpetas y módulos

```text
app.py              Interfaz Streamlit
config.py           Rutas y variables BOOK2ANKI_*
models.py           Source, Section, Card y el protocolo Enriquecedor
providers.py        Ollama, API o el proveedor falso
registro.py         Log de las llamadas al modelo en data/logs/ia.log
enriquecedores.py   Traducción, explicación, subtítulo y resumen de sección
db.py               SQLite
importers.py        Lectura, secciones, párrafos y vallas de código
exporter.py         TSV
tests/              pytest, sin red
ejemplos/           notas_ejemplo.md y con_codigo.md
docs/CONTEXTO.md    Reporte técnico
data/               Base y TSV generados; no forma parte del código
.streamlit/         Escucha en 127.0.0.1 y no envía estadísticas de uso
```

## 8. Datos y copia de seguridad

La base por defecto es `data/book2anki.db`. Guarda `sources`, `sections`, `cards`, `section_summaries` y `ai_cache`. Los TSV quedan en `data/exportaciones/`, con nombre `tarjetas_YYYYMMDD_HHMMSS.tsv`.

Para una copia de seguridad, copia ese archivo y esa carpeta con la aplicación cerrada. Restaurar es volver a ponerlos en su sitio.

## 9. Importar el TSV en Anki

Crea un tipo de nota cuyos campos estén en este orden, que es el de `COLUMNAS` en `exporter.py`:

1. `id`
2. `source`
3. `chapter`
4. `title`
5. `subtitle`
6. `lang`
7. `original_text`
8. `audio`
9. `translation`
10. `explanation`
11. `notes`
12. `tags`
13. `code`
14. `code_lang`

En Anki: Archivo, Importar, elige el `.tsv`, separador tabulador, y activa HTML en los campos. El mapeo debe seguir ese orden.

El archivo es UTF-8. Cada salto de línea del texto es `<br>` y cada tabulador interno es un espacio, para que una tarjeta ocupe una sola fila. Si la tarjeta tiene código, `code` es `<pre><code class="language-…">…</code></pre>`, también con `<br>` dentro. Si no hay código, `code` va vacío. `audio` va vacío hasta la etapa de audio.

Importar ese archivo dentro de Anki no se comprobó en esta máquina.

## 10. Solución de problemas

**`command not found: streamlit`.** El comando está en el entorno virtual. Actívalo con `source .venv/bin/activate` desde la raíz, o llama a `.venv/bin/streamlit`.

**Ollama no está en marcha.** La página dice «Ollama no está en marcha en http://127.0.0.1:11434. Arráncalo con ollama serve.» Comprueba con `curl -sS -m 5 http://127.0.0.1:11434/api/tags`.

**El modelo no está descargado.** Si Ollama responde y el modelo no está, la prueba dice «El modelo … no está descargado» e indica `ollama pull`.

**`ImportError` después de cambiar archivos, con la app abierta.** El proceso de Streamlit sigue con el código viejo. Ciérralo y vuelve a ejecutar `streamlit run app.py`.

**Un modelo de 7B o más.** Lectura avisa con la cifra de `BOOK2ANKI_RAM_GB`. Con `qwen2.5:3b`, o con el proveedor `falso`, esa línea no aparece.

**El resumen no sale.** La página dice la causa (cortado, no es JSON, faltan campos, tiempo agotado o salida repetida) y apunta a `data/logs/ia.log`. Ahí quedan el proveedor, el modelo, el tamaño del prompt, el tiempo y la respuesta cruda. El archivo no guarda claves.

## 11. Registro de cambios

Todo lo de esta lista es del 2026-10-07.

- **Etapa 1.** Importar `.md` y `.txt`, partir en secciones y párrafos, guardar tarjetas en SQLite y exportar TSV.
- **Etapa 1.5.** Borrar tarjetas, borrar una fuente y restablecer la base, con confirmación. Reimportar una ruta pregunta si se reemplaza o se añade otra.
- **Etapa 2.** Traducción y explicación con Ollama o con una API. Caché de respuestas ya válidas. La clave de la API solo vive en el entorno.
- **Etapa 3.** Modo estudio: resumen y tarjetas propuestas, sin escribir en `cards` hasta guardar. Vallas de código, columnas `code` y `code_lang`, y tabla `section_summaries`. El TSV pasa a 14 columnas.
- **Corrección de interfaz.** Anterior y Siguiente cambian la sección con un callback, antes de pintar el selector. El aviso de RAM solo aparece si el modelo es de 7B o más. En Mis tarjetas, Borrar y Generar van delante del resto de columnas, e `id` y `title` quedan fijas.
- **Resumen con Ollama.** El JSON único de resumen y tarjetas se parte en llamadas pequeñas. Ollama recibe `num_ctx` 4096, `temperature` 0.2, `num_predict` 512 o 768 y `repeat_penalty` 1.1. El código sale de las vallas. El fallo queda en `data/logs/ia.log`.
