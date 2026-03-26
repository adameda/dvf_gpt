from app.repositories import dvf_repository
from app.models.schemas import EvolutionResult, EvolutionDataPoint, Intent
from typing import Optional


def get_evolution(intent: Intent) -> Optional[EvolutionResult]:
    """Get price evolution over time for a location."""
    rows = dvf_repository.fetch_evolution(
        ville=intent.ville,
        departement=intent.departement,
        type_local=intent.type_local.value if intent.type_local else None,
    )

    if not rows:
        return None

    evolution = [
        EvolutionDataPoint(
            annee=int(row["annee"]),
            prix_median_m2=float(row["prix_median_m2"]),
            volume_transactions=int(row["volume_transactions"]),
        )
        for row in rows
    ]

    return EvolutionResult(
        ville=intent.ville or f"Département {intent.departement}",
        type_local=intent.type_local.value if intent.type_local else None,
        evolution=evolution,
    )


def format_summary(result: EvolutionResult) -> str:
    if len(result.evolution) < 2:
        return f"Données insuffisantes pour analyser l'évolution à {result.ville}."

    first = result.evolution[0]
    last = result.evolution[-1]
    variation = ((last.prix_median_m2 - first.prix_median_m2) / first.prix_median_m2) * 100

    direction = "hausse" if variation > 0 else "baisse"
    type_str = f" ({result.type_local}s)" if result.type_local else ""

    years_data = " | ".join(
        f"{p.annee}: {p.prix_median_m2:,.0f} €/m²"
        for p in result.evolution
    )

    return (
        f"Évolution des prix{type_str} à {result.ville} de {first.annee} à {last.annee} : "
        f"en {direction} de {abs(variation):.1f}%. {years_data}."
    )
