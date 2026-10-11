"""
polizas-api — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás.

Arranque:  alembic upgrade head  &&  uvicorn main:app --port 8000
"""
import hashlib
import pickle
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from config import Settings, get_settings
from database import get_db
from esquemas import (PolizaActualizacion, PolizaEntrada, PolizaSalida, PrediccionSalida,
                      PuntuacionEntrada, PuntuacionSalida, ResumenPoliza, Salud,
                      SiniestroEntrada, SiniestroSalida)
from modelos import Poliza, Prediccion, Siniestro

app = FastAPI(title="Pólizas API", version="1.0.0")


# --- Dependencias -----------------------------------------------------------------

@lru_cache
def get_modelo():
    """El modelo se carga una sola vez, la primera vez que se pide (no al importar)."""
    with open(get_settings().ruta_modelo, "rb") as fh:
        return pickle.load(fh)


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


def _poliza_o_404(db: Session, id_poliza: int) -> Poliza:
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {id_poliza}")
    return poliza


# --- Salud (B10) ------------------------------------------------------------------

@app.get("/health", response_model=Salud)
def salud(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Salud(estado="degradado", base_de_datos="sin conexión")
    return Salud(estado="ok", base_de_datos="ok")


# --- Pólizas ----------------------------------------------------------------------

@app.post("/polizas", response_model=PolizaSalida, status_code=status.HTTP_201_CREATED)
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    poliza = Poliza(**datos.model_dump(exclude={"siniestros"}),
                    token_firma=firmar(datos.numero, settings.secreto_firma))
    poliza.siniestros = [Siniestro(**s.model_dump()) for s in datos.siniestros]
    db.add(poliza)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # la sesión queda limpia; además es solo de esta petición
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"ya existe una póliza con número {datos.numero}")
    return PolizaSalida.model_validate(poliza)


@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Session = Depends(get_db)):
    # Estrategia: selectinload. Una consulta para las pólizas y otra (IN ...) para
    # todos sus siniestros, en vez de una consulta por póliza.
    polizas = db.scalars(
        select(Poliza).options(selectinload(Poliza.siniestros)).order_by(Poliza.id)).all()
    return [PolizaSalida.model_validate(p) for p in polizas]


@app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
    # Estrategia: lazy. Para UNA póliza son dos consultas igual que con selectinload:
    # la póliza, y sus siniestros cuando se leen al armar la respuesta.
    poliza = _poliza_o_404(db, id_poliza)
    return PolizaSalida.model_validate(poliza)


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida)
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)
    # H8: solo los campos que el cliente envió (y que no vienen en null).
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    nueva_fin = cambios.get("fecha_fin", poliza.fecha_fin)
    if nueva_fin <= poliza.fecha_inicio:
        raise HTTPException(status_code=422,
                            detail="fecha_fin debe ser posterior a fecha_inicio")
    for campo, valor in cambios.items():
        setattr(poliza, campo, valor)
    db.commit()
    return PolizaSalida.model_validate(poliza)


# --- Siniestros -------------------------------------------------------------------

@app.post("/polizas/{id_poliza}/siniestros", response_model=SiniestroSalida,
          status_code=status.HTTP_201_CREATED)
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)  # H13: 404 antes de tocar la base
    siniestro = Siniestro(poliza=poliza, **datos.model_dump())
    db.add(siniestro)
    db.commit()
    return SiniestroSalida.model_validate(siniestro)


@app.get("/siniestros", response_model=list[SiniestroSalida])
def listar_siniestros(db: Session = Depends(get_db)):
    # Estrategia: joinedload. Cada siniestro tiene UNA póliza, así que el JOIN no
    # multiplica filas: una sola consulta.
    siniestros = db.scalars(
        select(Siniestro).options(joinedload(Siniestro.poliza)).order_by(Siniestro.id)).all()
    return [SiniestroSalida.model_validate(s) for s in siniestros]


@app.get("/resumen", response_model=list[ResumenPoliza])
def resumen(db: Session = Depends(get_db)):
    # Estrategia: agregada. La base cuenta y suma con GROUP BY; no se cargan los
    # siniestros en memoria.
    filas = db.execute(
        select(Poliza.numero,
               func.count(Siniestro.id).label("n_siniestros"),
               func.coalesce(func.sum(Siniestro.monto), 0).label("monto_total"))
        .outerjoin(Siniestro, Siniestro.poliza_id == Poliza.id)
        .group_by(Poliza.id, Poliza.numero)
        .order_by(Poliza.id)).all()
    return [ResumenPoliza(numero=f.numero, n_siniestros=f.n_siniestros,
                          monto_total=round(f.monto_total, 2)) for f in filas]


# --- Puntuación -------------------------------------------------------------------

@app.post("/score", response_model=PuntuacionSalida)
def puntuar(datos: PuntuacionEntrada, db: Session = Depends(get_db),
            settings: Settings = Depends(get_settings), modelo=Depends(get_modelo)):
    poliza = db.scalar(select(Poliza).options(selectinload(Poliza.siniestros))
                       .where(Poliza.numero == datos.numero))
    if poliza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {datos.numero}")
    rasgos = [[poliza.prima, len(poliza.siniestros), sum(s.monto for s in poliza.siniestros),
               (date.today() - poliza.fecha_inicio).days]]
    puntaje = float(modelo.predict_proba(rasgos)[0][1])
    alto_riesgo = puntaje > settings.umbral_alto_riesgo
    db.add(Prediccion(poliza_id=poliza.id, puntaje=puntaje, alto_riesgo=alto_riesgo))
    db.commit()
    return PuntuacionSalida(numero=poliza.numero, puntaje=round(puntaje, 4), alto_riesgo=alto_riesgo)


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Session = Depends(get_db)):
    predicciones = db.scalars(
        select(Prediccion).options(joinedload(Prediccion.poliza)).order_by(Prediccion.id)).all()
    return [PrediccionSalida.model_validate(p) for p in predicciones]
