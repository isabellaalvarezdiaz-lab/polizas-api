"""
Batería corregida de `ia_tests_propuesta.py` (Parte D).

    pytest tests/test_ia_corregido.py -v

Qué cambia frente a la propuesta de la IA:
  1. Cada assert exige el código exacto del contrato (201, 404, 409, 422), no
     una tupla de códigos que acepta el error que se quiere detectar.
  2. El aislamiento es real: se sustituye `database.get_db` (no una función con
     el mismo nombre definida aquí) por una sesión sobre una base temporal
     nueva en cada test, y se comprueba que la escritura llegó a esa base.
  3. Los datos son fijos y van parametrizados: sin `random`, el test da el mismo
     resultado en cada corrida y siempre recorre los mismos casos.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
# Si nadie fijó DATABASE_URL, apuntamos a una base desechable: así ni siquiera la
# importación de la aplicación puede tocar la base real.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp()) / 'importacion.db'}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import database  # noqa: E402
import modelos  # noqa: E402,F401  (registra las tablas en Base.metadata)
from main import app  # noqa: E402


# --- Aislamiento real ----------------------------------------------------------

@pytest.fixture
def sesiones(tmp_path):
    """Base SQLite nueva para cada test, con claves foráneas activas."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}",
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    database.Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = _get_db
    yield Sesion
    app.dependency_overrides.pop(database.get_db, None)
    engine.dispose()


@pytest.fixture
def cliente(sesiones):
    return TestClient(app, raise_server_exceptions=False)


# --- Datos fijos ---------------------------------------------------------------

def _poliza(numero="POL-IA-00001", **extra) -> dict:
    base = {
        "numero": numero,
        "asegurado": "Prueba Automática",
        "tipo": "auto",
        "prima": 1_250_000,
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-12-31",
    }
    base.update(extra)
    return base


def _crear(cliente, **extra) -> dict:
    r = cliente.post("/polizas", json=_poliza(**extra))
    assert r.status_code == 201, f"crear devolvió {r.status_code}: {r.text}"
    return r.json()


# --- Creación ------------------------------------------------------------------

def test_crear_poliza_devuelve_201_y_queda_guardada(cliente, sesiones):
    creada = _crear(cliente)
    assert creada["numero"] == "POL-IA-00001"
    assert creada["asegurado"] == "Prueba Automática"
    assert "token_firma" not in creada

    # La póliza se puede leer de vuelta...
    leida = cliente.get(f"/polizas/{creada['id']}")
    assert leida.status_code == 200
    assert leida.json()["numero"] == "POL-IA-00001"

    # ...y quedó en la base TEMPORAL: el aislamiento es real.
    with sesiones() as db:
        assert db.scalar(select(func.count()).select_from(modelos.Poliza)) == 1


@pytest.mark.parametrize("numero, tipo, prima", [
    ("POL-IA-10001", "auto", 1),
    ("POL-IA-10002", "hogar", 1_250_000.5),
    ("POL-IA-10003", "vida", 4_999_999.99),
])
def test_primas_variadas_son_aceptadas(cliente, numero, tipo, prima):
    creada = _crear(cliente, numero=numero, tipo=tipo, prima=prima)
    assert creada["tipo"] == tipo
    assert creada["prima"] == pytest.approx(prima)


@pytest.mark.parametrize("extra", [
    {"prima": 0},
    {"prima": -10},
    {"fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"},
    {"siniestros": [{"fecha": "2026-03-02", "monto": -50, "descripcion": "Choque leve"}]},
], ids=["prima_cero", "prima_negativa", "fechas_invertidas", "siniestro_negativo"])
def test_entrada_invalida_da_422(cliente, extra):
    assert cliente.post("/polizas", json=_poliza(**extra)).status_code == 422


def test_numero_duplicado_da_409(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=_poliza()).status_code == 409
    # y el servicio sigue respondiendo después del conflicto
    assert cliente.get("/polizas").status_code == 200


# --- Consulta y errores --------------------------------------------------------

def test_poliza_inexistente_da_404(cliente):
    assert cliente.get("/polizas/999999").status_code == 404
    assert cliente.put("/polizas/999999", json={"prima": 10}).status_code == 404
    siniestro = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve"}
    assert cliente.post("/polizas/999999/siniestros", json=siniestro).status_code == 404
    assert cliente.post("/score", json={"numero": "POL-NO-EXISTE"}).status_code == 404


def test_listar_polizas_incluye_la_creada(cliente):
    _crear(cliente)
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert [p["numero"] for p in r.json()] == ["POL-IA-00001"]


def test_resumen_cuenta_y_suma_por_poliza(cliente):
    _crear(cliente, siniestros=[
        {"fecha": "2026-03-02", "monto": 100, "descripcion": "Choque leve"},
        {"fecha": "2026-04-10", "monto": 250, "descripcion": "Vidrio roto"},
    ])
    r = cliente.get("/resumen")
    assert r.status_code == 200
    fila = next(f for f in r.json() if f["numero"] == "POL-IA-00001")
    assert fila["n_siniestros"] == 2
    assert fila["monto_total"] == pytest.approx(350)


# --- Puntuación ----------------------------------------------------------------

def test_score_de_poliza_recien_creada(cliente):
    _crear(cliente)
    r = cliente.post("/score", json={"numero": "POL-IA-00001"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert 0.0 <= cuerpo["puntaje"] <= 1.0
    assert isinstance(cuerpo["alto_riesgo"], bool)

    registradas = cliente.get("/predicciones").json()
    assert any(p["numero"] == "POL-IA-00001" for p in registradas)

