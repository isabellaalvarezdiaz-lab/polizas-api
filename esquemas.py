"""Esquemas de entrada (B7) y de salida (B4, B6)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIPOS = r"^(auto|hogar|vida)$"
ESTADOS = r"^(abierto|pagado|rechazado)$"


def _normalizar_nombre(v: str) -> str:
    """Quita espacios sobrantes y pone el nombre con mayúscula inicial."""
    return " ".join(v.split()).title()


# --- Entrada -------------------------------------------------------------------

class SiniestroEntrada(BaseModel):
    fecha: date
    monto: float = Field(gt=0, description="Monto reclamado, en pesos")
    descripcion: str = Field(min_length=3, max_length=200)
    estado: str = Field(default="abierto", pattern=ESTADOS)


class PolizaEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")
    asegurado: str = Field(min_length=3, max_length=80)
    tipo: str = Field(pattern=TIPOS, description="auto, hogar o vida")
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
    """PUT parcial: todos los campos son opcionales y solo se aplica lo enviado (H8)."""
    asegurado: Optional[str] = Field(default=None, min_length=3, max_length=80)
    tipo: Optional[str] = Field(default=None, pattern=TIPOS)
    prima: Optional[float] = Field(default=None, gt=0)
    fecha_fin: Optional[date] = None

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalizar_nombre(v)


class PuntuacionEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20)


# --- Salida (lo único que el cliente puede ver) ----------------------------------

class SiniestroEnPoliza(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    monto: float
    descripcion: str
    estado: str


class PolizaSalida(BaseModel):
    """Sin token_firma (H3)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    asegurado: str
    tipo: str
    prima: float
    fecha_inicio: date
    fecha_fin: date
    siniestros: list[SiniestroEnPoliza]


class SiniestroSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int
    numero_poliza: str
    fecha: date
    monto: float
    descripcion: str
    estado: str


class ResumenPoliza(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero: str
    n_siniestros: int
    monto_total: float


class PuntuacionSalida(BaseModel):
    numero: str
    puntaje: float = Field(ge=0, le=1)
    alto_riesgo: bool


class PrediccionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int
    numero: str
    puntaje: float
    alto_riesgo: bool
    creado_en: datetime


class Salud(BaseModel):
    estado: str
    base_de_datos: str
