"""Navegación entre secciones y aviso de modelos grandes, sin base."""

from app import _ORDEN_TABLA, _modelo_grande, id_vecino


def test_id_vecino_en_los_extremos() -> None:
    ids = [10, 20, 30]
    assert id_vecino(ids, 10, -1) is None
    assert id_vecino(ids, 10, 1) == 20
    assert id_vecino(ids, 30, 1) is None
    assert id_vecino(ids, 30, -1) == 20
    assert id_vecino(ids, 20, -1) == 10
    assert id_vecino(ids, 20, 1) == 30
    assert id_vecino(ids, 99, 1) is None


def test_modelo_grande_desde_7b() -> None:
    assert _modelo_grande("qwen2.5:3b") is False
    assert _modelo_grande("falso") is False
    assert _modelo_grande("qwen2.5:7b") is True
    assert _modelo_grande("qwen2.5:14b") is True


def test_borrar_y_generar_van_primero() -> None:
    assert _ORDEN_TABLA[:2] == ("borrar", "generar")
    assert "id" in _ORDEN_TABLA
    assert "title" in _ORDEN_TABLA
