"""Esquemas de entrada."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalizar_nombre(v: str) -> str:
    """Quita espacios sobrantes y pone el nombre con mayúscula inicial."""
    return " ".join(v.split()).title()


class SiniestroEntrada(BaseModel):
    fecha: date
    monto: float = Field(gt=0, description="Monto reclamado, en pesos")
    descripcion: str = Field(min_length=3, max_length=200)
    estado: str = "abierto"


class PolizaEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")
    asegurado: str = Field(min_length=3, max_length=80)
    tipo: str = Field(description="auto, hogar o vida")
    prima: float = Field(gt=0, description="Prima anual, en pesos")
    fecha_inicio: date
    fecha_fin: date
    # H5: los siniestros anidados pasan por las mismas reglas que uno suelto.
    siniestros: list[SiniestroEntrada] = Field(default_factory=list,
                                               description="Siniestros ya declarados")

    # H4: el validador DEVUELVE el valor normalizado.
    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: str) -> str:
        return _normalizar_nombre(v)

    # H6: compara dos campos, por eso es model_validator y no field_validator.
    @model_validator(mode="after")
    def fechas_coherentes(self) -> "PolizaEntrada":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PolizaActualizacion(BaseModel):
    asegurado: Optional[str] = Field(default=None, min_length=3, max_length=80)
    tipo: Optional[str] = None
    prima: Optional[float] = Field(default=None, gt=0)
    fecha_fin: Optional[date] = None

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalizar_nombre(v)


class PuntuacionEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20)