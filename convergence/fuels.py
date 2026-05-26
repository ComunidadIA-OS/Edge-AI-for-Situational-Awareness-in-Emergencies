from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FuelTypeId = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

_STANDARD_CP = 2000.0
_STANDARD_DELTA_H = 18_600_000.0
_STANDARD_TI = 600.0


@dataclass(frozen=True)
class FuelModel:
    fuel_type_id: int
    name: str
    description: str
    rhod: float
    rhol: float
    sd: float
    sl: float
    e: float
    sigmad: float
    sigmal: float
    delta_h: float = _STANDARD_DELTA_H
    cp: float = _STANDARD_CP
    ti: float = _STANDARD_TI

    def to_dict(self) -> dict:
        return {
            "fuel_type_id": self.fuel_type_id,
            "name": self.name,
            "description": self.description,
            "rhod": self.rhod,
            "rhol": self.rhol,
            "sd": self.sd,
            "sl": self.sl,
            "e": self.e,
            "sigmad": self.sigmad,
            "sigmal": self.sigmal,
            "delta_h": self.delta_h,
            "cp": self.cp,
            "ti": self.ti,
        }


FUEL_MODELS: dict[int, FuelModel] = {
    1: FuelModel(
        fuel_type_id=1,
        name="Short Grass",
        description="Pastizales bajos (<30 cm). Propagacion rapida con viento. Comun en praderas y sabanas.",
        rhod=512.0,
        rhol=512.0,
        sd=11500.0,
        sl=4900.0,
        e=0.30,
        sigmad=0.17,
        sigmal=0.0,
    ),
    2: FuelModel(
        fuel_type_id=2,
        name="Timber Grass",
        description="Pastizal bajo dosel arboreo abierto. Menor velocidad de viento efectiva por proteccion del dosel.",
        rhod=512.0,
        rhol=512.0,
        sd=9800.0,
        sl=4900.0,
        e=0.30,
        sigmad=0.45,
        sigmal=0.02,
    ),
    3: FuelModel(
        fuel_type_id=3,
        name="Tall Grass",
        description="Pastizales altos (75-100 cm). Carga de combustible elevada, propagacion muy rapida con viento fuerte.",
        rhod=512.0,
        rhol=512.0,
        sd=4900.0,
        sl=4900.0,
        e=0.75,
        sigmad=0.67,
        sigmal=0.0,
    ),
    4: FuelModel(
        fuel_type_id=4,
        name="Chaparral",
        description="Matorral denso mediterraneo (>2 m). Alta carga de combustible vivo y muerto. Comportamiento extremo con viento.",
        rhod=512.0,
        rhol=512.0,
        sd=6600.0,
        sl=4900.0,
        e=1.80,
        sigmad=2.24,
        sigmal=1.12,
    ),
    5: FuelModel(
        fuel_type_id=5,
        name="Brush",
        description="Arbustos bajos (<1 m). Carga ligera de combustible. Propagacion moderada.",
        rhod=512.0,
        rhol=512.0,
        sd=5600.0,
        sl=4900.0,
        e=0.60,
        sigmad=0.22,
        sigmal=0.07,
    ),
    6: FuelModel(
        fuel_type_id=6,
        name="Dormant Brush",
        description="Arbustivo latente o hardwood slash. Combustible muerto predominante. Alta inflamabilidad en sequia.",
        rhod=512.0,
        rhol=512.0,
        sd=5600.0,
        sl=4900.0,
        e=0.75,
        sigmad=0.67,
        sigmal=0.0,
    ),
    7: FuelModel(
        fuel_type_id=7,
        name="Southern Rough",
        description="Sotobosque del sudeste de EE.UU. Hojarasca de pino con arbustos bajos. Alta relacion superficie/volumen.",
        rhod=512.0,
        rhol=512.0,
        sd=5800.0,
        sl=4900.0,
        e=0.25,
        sigmad=0.25,
        sigmal=0.05,
    ),
    8: FuelModel(
        fuel_type_id=8,
        name="Closed Timber Litter",
        description="Hojarasca compacta bajo dosel cerrado. Baja propagacion salvo con vientos fuertes o sequia extrema.",
        rhod=512.0,
        rhol=512.0,
        sd=5900.0,
        sl=4900.0,
        e=0.06,
        sigmad=0.67,
        sigmal=0.0,
    ),
    9: FuelModel(
        fuel_type_id=9,
        name="Hardwood Litter",
        description="Hojarasca de frondosas caducifolias. Compactacion alta, baja inflamabilidad excepto en otoño seco.",
        rhod=512.0,
        rhol=512.0,
        sd=6600.0,
        sl=4900.0,
        e=0.05,
        sigmad=0.65,
        sigmal=0.0,
    ),
    10: FuelModel(
        fuel_type_id=10,
        name="Timber Litter & Understory",
        description="Hojarasca de coniferas con sotobosque. Carga media de combustible. Comun en bosques de pino ponderosa.",
        rhod=512.0,
        rhol=512.0,
        sd=5900.0,
        sl=4900.0,
        e=0.30,
        sigmad=1.12,
        sigmal=0.22,
    ),
    11: FuelModel(
        fuel_type_id=11,
        name="Light Slash",
        description="Restos ligeros de tala (<7.5 cm diametro). Alta relacion superficie/volumen. Secado rapido.",
        rhod=512.0,
        rhol=512.0,
        sd=4900.0,
        sl=4900.0,
        e=0.30,
        sigmad=2.24,
        sigmal=0.0,
    ),
    12: FuelModel(
        fuel_type_id=12,
        name="Medium Slash",
        description="Restos medios de tala (7.5-20 cm). Carga sustancial. Propagacion moderada con mayor duracion.",
        rhod=512.0,
        rhol=512.0,
        sd=4900.0,
        sl=4900.0,
        e=0.70,
        sigmad=3.36,
        sigmal=0.0,
    ),
    13: FuelModel(
        fuel_type_id=13,
        name="Heavy Slash",
        description="Restos pesados de tala (>20 cm). Carga muy alta. Propagacion lenta pero extrema intensidad y duracion.",
        rhod=512.0,
        rhol=512.0,
        sd=4900.0,
        sl=4900.0,
        e=1.00,
        sigmad=4.49,
        sigmal=0.0,
    ),
}


def get_fuel_model(fuel_type_id: int) -> FuelModel | None:
    return FUEL_MODELS.get(fuel_type_id)


def get_fuel_model_or_default(fuel_type_id: int, default_id: int = 1) -> FuelModel:
    return FUEL_MODELS.get(fuel_type_id, FUEL_MODELS[default_id])


def list_fuel_models() -> list[FuelModel]:
    return list(FUEL_MODELS.values())
