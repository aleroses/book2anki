"""Partición de Markdown con vallas de código. No usa la base."""

from importers import codigo_de_parrafo, partir_parrafos, partir_secciones

_NOTA = """# Capítulo

Texto de la sección.

```bash
# comando ls

ls -l
```

## Otra

Después.
"""


def test_bash_no_parte_la_seccion_ni_el_parrafo() -> None:
    secciones = partir_secciones(_NOTA)
    assert len(secciones) == 2
    assert secciones[0].heading == "Capítulo"
    assert secciones[1].heading == "Otra"
    assert "# comando ls" in secciones[0].body
    parrafos = partir_parrafos(secciones[0].body)
    bloques = [parrafo for parrafo in parrafos if "comando ls" in parrafo]
    assert len(bloques) == 1
    assert bloques[0].startswith("```bash")
    assert "ls -l" in bloques[0]
    assert "\n\n" in bloques[0]
    assert codigo_de_parrafo(bloques[0]) == ("bash", "# comando ls\n\nls -l")
    assert "Texto de la sección." in parrafos


def test_valla_abierta_no_rompe() -> None:
    texto = "# Título\n\nantes\n\n```bash\n# comando ls\n\nno cierra\n\n# Falso\n"
    secciones = partir_secciones(texto)
    assert len(secciones) == 1
    assert secciones[0].heading == "Título"
    assert "# Falso" in secciones[0].body
    parrafos = partir_parrafos(secciones[0].body)
    assert "antes" in parrafos
    assert any("# Falso" in parrafo and "comando ls" in parrafo for parrafo in parrafos)


def test_valla_de_virgulillas() -> None:
    texto = "~~~python\n# no es título\n\nprint(1)\n~~~\n"
    secciones = partir_secciones(texto)
    assert len(secciones) == 1
    parrafos = partir_parrafos(secciones[0].body)
    assert len(parrafos) == 1
    assert codigo_de_parrafo(parrafos[0]) == ("python", "# no es título\n\nprint(1)")
