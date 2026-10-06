"""
polizas-api-v0 — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.
"""
import hashlib
import pickle
from datetime import date

from fastapi import FastAPI
from sqlalchemy import select

import config
from database import Base, engine, sesion
from esquemas import PolizaActualizacion, PolizaEntrada, PuntuacionEntrada, SiniestroEntrada
from modelos import Poliza, Prediccion, Siniestro

Base.metadata.create_all(engine)

with open(config.RUTA_MODELO, "rb") as fh:
    modelo = pickle.load(fh)

app = FastAPI(title="Pólizas API", version="0.1.0")


def firmar(numero: str) -> str:
    return hashlib.sha256(f"{numero}:{config.SECRETO_FIRMA}".encode()).hexdigest()


def _siniestro(s: Siniestro) -> dict:
    return {"id": s.id, "poliza_id": s.poliza_id, "numero_poliza": s.poliza.numero,
            "fecha": s.fecha, "monto": s.monto, "descripcion": s.descripcion, "estado": s.estado}


def _poliza(p: Poliza) -> dict:
    return {
        "id": p.id, "numero": p.numero, "asegurado": p.asegurado, "tipo": p.tipo,
        "prima": p.prima, "fecha_inicio": p.fecha_inicio, "fecha_fin": p.fecha_fin,
        "token_firma": p.token_firma,
        "siniestros": [{"id": s.id, "fecha": s.fecha, "monto": s.monto,
                        "descripcion": s.descripcion, "estado": s.estado} for s in p.siniestros],
    }


@app.post("/polizas")
def crear_poliza(datos: PolizaEntrada):
    poliza = Poliza(numero=datos.numero, asegurado=datos.asegurado, tipo=datos.tipo,
                    prima=datos.prima, fecha_inicio=datos.fecha_inicio, fecha_fin=datos.fecha_fin,
                    token_firma=firmar(datos.numero))
    for s in datos.siniestros:
        poliza.siniestros.append(Siniestro(
            fecha=s.fecha, monto=s.monto, descripcion=s.descripcion, estado=s.estado))
    sesion.add(poliza)
    sesion.commit()
    sesion.refresh(poliza)
    return poliza


@app.get("/polizas")
def listar_polizas():
    return [_poliza(p) for p in sesion.scalars(select(Poliza).order_by(Poliza.id))]


@app.get("/polizas/{id_poliza}")
def obtener_poliza(id_poliza: int):
    poliza = sesion.get(Poliza, id_poliza)
    if poliza is None:
        return {"error": f"no existe la póliza {id_poliza}"}
    return _poliza(poliza)


@app.put("/polizas/{id_poliza}")
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion):
    poliza = sesion.get(Poliza, id_poliza)
    if poliza is None:
        return {"error": f"no existe la póliza {id_poliza}"}
    for campo, valor in datos.model_dump().items():
        setattr(poliza, campo, valor)
    sesion.commit()
    sesion.refresh(poliza)
    return _poliza(poliza)


@app.post("/polizas/{id_poliza}/siniestros")
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada):
    siniestro = Siniestro(poliza_id=id_poliza, fecha=datos.fecha, monto=datos.monto,
                          descripcion=datos.descripcion, estado=datos.estado)
    sesion.add(siniestro)
    sesion.commit()
    sesion.refresh(siniestro)
    return {"id": siniestro.id, "poliza_id": siniestro.poliza_id, "fecha": siniestro.fecha,
            "monto": siniestro.monto, "descripcion": siniestro.descripcion, "estado": siniestro.estado}


@app.get("/siniestros")
def listar_siniestros():
    return [_siniestro(s) for s in sesion.scalars(select(Siniestro).order_by(Siniestro.id))]


@app.get("/resumen")
def resumen():
    filas = []
    for p in sesion.scalars(select(Poliza).order_by(Poliza.id)):
        filas.append({"numero": p.numero, "n_siniestros": len(p.siniestros),
                      "monto_total": round(sum(s.monto for s in p.siniestros), 2)})
    return filas


@app.post("/score")
def puntuar(datos: PuntuacionEntrada):
    poliza = sesion.scalar(select(Poliza).where(Poliza.numero == datos.numero))
    if poliza is None:
        return {"error": f"no existe la póliza {datos.numero}"}
    rasgos = [[poliza.prima, len(poliza.siniestros), sum(s.monto for s in poliza.siniestros),
               (date.today() - poliza.fecha_inicio).days]]
    puntaje = float(modelo.predict_proba(rasgos)[0][1])
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje,
                            alto_riesgo=puntaje > config.UMBRAL_ALTO_RIESGO)
    sesion.add(prediccion)
    sesion.commit()
    return {"numero": poliza.numero, "puntaje": round(puntaje, 4),
            "alto_riesgo": prediccion.alto_riesgo}


@app.get("/predicciones")
def listar_predicciones():
    return [{"id": pr.id, "poliza_id": pr.poliza_id, "puntaje": pr.puntaje,
             "alto_riesgo": pr.alto_riesgo, "creado_en": pr.creado_en}
            for pr in sesion.scalars(select(Prediccion).order_by(Prediccion.id))]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
