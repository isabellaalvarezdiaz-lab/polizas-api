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
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import database  # noqa: E402
import modelos  # noqa: E402,F401  (registra las tablas en Base.metadata)
from main import app  # noqa: E402


# --- Aislamiento real ----------------------------------------------------------

@pytest.fixture
def sesiones(tmp_path):
    """Base SQLite nueva para cada test, con claves foráneas activas."""
    # Mismo constructor que usa la aplicación: activa PRAGMA foreign_keys en cada conexión.
    engine = database.crear_engine(f"sqlite:///{tmp_path / 'test.db'}")
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
    {"tipo": "moto"},
    {"fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"},
    {"fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-01"},
    {"siniestros": [{"fecha": "2026-03-02", "monto": -50, "descripcion": "Choque leve"}]},
], ids=["prima_cero", "prima_negativa", "tipo_invalido", "fechas_invertidas",
        "fechas_iguales", "siniestro_negativo"])
def test_entrada_invalida_da_422(cliente, sesiones, extra):
    assert cliente.post("/polizas", json=_poliza(**extra)).status_code == 422
    # y no quedó nada guardado
    with sesiones() as db:
        assert db.scalar(select(func.count()).select_from(modelos.Poliza)) == 0


def test_asegurado_se_normaliza(cliente):
    creada = _crear(cliente, asegurado="  ana   rueda ")
    assert creada["asegurado"] == "Ana Rueda"
    leida = cliente.get(f"/polizas/{creada['id']}").json()
    assert leida["asegurado"] == "Ana Rueda"


def test_numero_duplicado_da_409(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=_poliza()).status_code == 409
    # y el servicio sigue respondiendo después del conflicto
    assert cliente.get("/polizas").status_code == 200


# --- Actualización y siniestros -------------------------------------------------

def test_put_parcial_queda_guardado_y_conserva_lo_demas(cliente):
    creada = _crear(cliente)
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200
    leida = cliente.get(f"/polizas/{creada['id']}").json()
    assert leida["prima"] == pytest.approx(999_000)
    assert leida["tipo"] == "auto"
    assert leida["fecha_fin"] == "2026-12-31"


def test_put_con_fecha_fin_anterior_da_422_y_no_cambia(cliente):
    creada = _crear(cliente)
    r = cliente.put(f"/polizas/{creada['id']}", json={"fecha_fin": "2025-06-01"})
    assert r.status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json()["fecha_fin"] == "2026-12-31"


def test_declarar_siniestro_da_201_y_queda_guardado(cliente):
    creada = _crear(cliente)
    siniestro = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve"}
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=siniestro)
    assert r.status_code == 201
    assert r.json()["numero_poliza"] == "POL-IA-00001"

    leida = cliente.get(f"/polizas/{creada['id']}").json()
    assert [s["monto"] for s in leida["siniestros"]] == [pytest.approx(850_000)]
    listado = cliente.get("/siniestros").json()
    assert [s["numero_poliza"] for s in listado] == ["POL-IA-00001"]


def test_siniestro_suelto_con_monto_negativo_da_422(cliente):
    creada = _crear(cliente)
    malo = {"fecha": "2026-03-02", "monto": -1, "descripcion": "Choque leve"}
    assert cliente.post(f"/polizas/{creada['id']}/siniestros", json=malo).status_code == 422


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
