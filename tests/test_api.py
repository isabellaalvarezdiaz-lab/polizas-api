"""Pruebas propias del servicio (B8).

    pytest tests/test_api.py

Cada test usa una base SQLite NUEVA en una carpeta temporal: la sesión de la
aplicación se sustituye con `app.dependency_overrides[database.get_db]`. Así los
tests pasan igual dos veces seguidas y la base de la aplicación no cambia.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
# Antes de importar la aplicación: si nadie fijó DATABASE_URL, el motor de la
# aplicación apunta a una base desechable y no a app.db.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp()) / 'importacion.db'}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import database  # noqa: E402
import modelos  # noqa: E402,F401
from main import app  # noqa: E402

POLIZA = {
    "numero": "POL-TEST-00001",
    "asegurado": "  prueba   interna ",
    "tipo": "auto",
    "prima": 1_000_000,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-12-31",
}
SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve"}


@pytest.fixture
def cliente(tmp_path):
    engine = database.crear_engine(f"sqlite:///{tmp_path / 'test.db'}")  # con foreign_keys=ON
    database.Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = _get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(database.get_db, None)
    engine.dispose()


def _crear(cliente, **extra):
    r = cliente.post("/polizas", json={**POLIZA, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["base_de_datos"] == "ok"


def test_crear_normaliza_el_nombre_y_no_expone_el_token(cliente):
    creada = _crear(cliente)
    assert creada["asegurado"] == "Prueba Interna"
    assert "token_firma" not in creada


def test_listar_incluye_la_creada(cliente):
    _crear(cliente)
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert [p["numero"] for p in r.json()] == ["POL-TEST-00001"]


def test_numero_duplicado_da_409_y_el_servicio_sigue(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=POLIZA).status_code == 409
    assert cliente.get("/polizas").status_code == 200


def test_put_parcial_conserva_lo_no_enviado(cliente):
    creada = _crear(cliente)
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["prima"] == 999_000
    assert cuerpo["tipo"] == "auto" and cuerpo["fecha_fin"] == "2026-12-31"


def test_put_con_fecha_fin_anterior_da_422(cliente):
    creada = _crear(cliente)
    assert cliente.put(f"/polizas/{creada['id']}", json={"fecha_fin": "2025-01-01"}).status_code == 422


def test_siniestro_201_y_404(cliente):
    creada = _crear(cliente)
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201
    assert r.json()["numero_poliza"] == "POL-TEST-00001"
    assert cliente.post("/polizas/999999/siniestros", json=SINIESTRO).status_code == 404


def test_resumen_cuenta_y_suma(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}])
    fila = cliente.get("/resumen").json()[0]
    assert fila == {"numero": "POL-TEST-00001", "n_siniestros": 2, "monto_total": 1_000_000}
