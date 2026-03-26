from app.services.dvf import comparables_service
from app.models.schemas import EstimationResult, Intent
from typing import Optional


def get_estimation(intent: Intent) -> Optional[EstimationResult]:
    """Estimate property value using comparables."""
    if not intent.ville or not intent.surface:
        return None

    comparables = comparables_service.get_comparables(intent)
    if not comparables or comparables.count == 0:
        return None

    prix_median_m2 = comparables.prix_median_m2
    surface = intent.surface

    # Apply ±10% confidence interval
    estimation_centrale = prix_median_m2 * surface
    estimation_basse = estimation_centrale * 0.90
    estimation_haute = estimation_centrale * 1.10

    return EstimationResult(
        ville=intent.ville,
        type_local=comparables.type_local,
        surface=surface,
        estimation_basse=round(estimation_basse, -3),
        estimation_haute=round(estimation_haute, -3),
        estimation_centrale=round(estimation_centrale, -3),
        prix_median_m2=prix_median_m2,
        nb_comparables=comparables.count,
        comparables=comparables.transactions[:10],
    )


def format_summary(result: EstimationResult) -> str:
    return (
        f"Estimation pour un {result.type_local.lower()} de {result.surface}m² à {result.ville} : "
        f"valeur estimée entre {result.estimation_basse:,.0f} € et {result.estimation_haute:,.0f} €, "
        f"soit {result.estimation_centrale:,.0f} € en valeur centrale. "
        f"Basé sur {result.nb_comparables} transactions comparables "
        f"à {result.prix_median_m2:,.0f} €/m²."
    )
