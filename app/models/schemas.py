from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class IntentType(str, Enum):
    PRIX_M2 = "prix_m2"
    COMPARABLES = "comparables"
    ESTIMATION = "estimation"
    EVOLUTION = "evolution"
    COMPARAISON = "comparaison"
    UNKNOWN = "unknown"


class TypeLocal(str, Enum):
    APPARTEMENT = "Appartement"
    MAISON = "Maison"


class Intent(BaseModel):
    type: IntentType
    ville: Optional[str] = None
    departement: Optional[str] = None
    type_local: Optional[TypeLocal] = None
    surface: Optional[float] = None
    annee: Optional[int] = None
    ville_comparaison: Optional[str] = None
    departement_comparaison: Optional[str] = None
    type_local_comparaison: Optional[TypeLocal] = None
    periode_debut: Optional[int] = None
    periode_fin: Optional[int] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PrixM2Result(BaseModel):
    ville: str
    type_local: Optional[str]
    prix_median_m2: float
    prix_moyen_m2: float
    volume_transactions: int
    prix_min_m2: float
    prix_max_m2: float
    annee: Optional[int]
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ComparableTransaction(BaseModel):
    id_mutation: str
    date_mutation: str
    valeur_fonciere: float
    surface_reelle_bati: float
    nombre_pieces_principales: Optional[int]
    nom_commune: str
    type_local: str
    latitude: float
    longitude: float
    prix_m2: float


class ComparablesResult(BaseModel):
    ville: str
    type_local: str
    surface: float
    transactions: list[ComparableTransaction]
    prix_median_m2: float
    count: int


class EstimationResult(BaseModel):
    ville: str
    type_local: str
    surface: float
    estimation_basse: float
    estimation_haute: float
    estimation_centrale: float
    prix_median_m2: float
    nb_comparables: int
    comparables: list[ComparableTransaction]


class EvolutionDataPoint(BaseModel):
    annee: int
    prix_median_m2: float
    volume_transactions: int


class EvolutionResult(BaseModel):
    ville: str
    type_local: Optional[str]
    evolution: list[EvolutionDataPoint]


class ComparaisonZone(BaseModel):
    zone: str
    type_local: Optional[str]
    prix_median_m2: float
    volume_transactions: int


class ComparaisonResult(BaseModel):
    zone_a: ComparaisonZone
    zone_b: ComparaisonZone
    difference_pct: float


class ChatResponse(BaseModel):
    intent: IntentType
    message: str
    data_type: Literal["prix_m2", "comparables", "estimation", "evolution", "comparaison", "error", "unknown"]
    data: Optional[dict] = None
    visualisation: Optional[Literal["map", "chart_line", "chart_bar", "cards", "map_comparables"]] = None
    debug: Optional[dict] = None
