from app.repositories import dvf_repository
from app.models.schemas import PrixM2Result, Intent
from typing import Optional


def get_prix_m2(intent: Intent) -> Optional[PrixM2Result]:
    """Get prix m² for a location based on intent."""
    rows = dvf_repository.fetch_prix_m2(
        ville=intent.ville,
        departement=intent.departement,
        type_local=intent.type_local.value if intent.type_local else None,
        annee=intent.annee,
    )

    if not rows:
        return None

    # Take the first row (most transactions)
    row = rows[0]
    return PrixM2Result(
        ville=row["nom_commune"],
        type_local=row.get("type_local"),
        prix_median_m2=float(row["prix_median_m2"]),
        prix_moyen_m2=float(row["prix_moyen_m2"]),
        volume_transactions=int(row["volume_transactions"]),
        prix_min_m2=float(row["prix_min_m2"]),
        prix_max_m2=float(row["prix_max_m2"]),
        annee=row.get("annee"),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
    )


def get_prix_m2_all_types(intent: Intent) -> list[PrixM2Result]:
    """Get prix m² for all property types in a location."""
    rows = dvf_repository.fetch_prix_m2(
        ville=intent.ville,
        departement=intent.departement,
        annee=intent.annee,
    )

    results = []
    for row in rows:
        results.append(PrixM2Result(
            ville=row["nom_commune"],
            type_local=row.get("type_local"),
            prix_median_m2=float(row["prix_median_m2"]),
            prix_moyen_m2=float(row["prix_moyen_m2"]),
            volume_transactions=int(row["volume_transactions"]),
            prix_min_m2=float(row["prix_min_m2"]),
            prix_max_m2=float(row["prix_max_m2"]),
            annee=row.get("annee"),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
        ))
    return results


def format_summary(result: PrixM2Result) -> str:
    type_str = f"{result.type_local}s" if result.type_local else "tous biens"
    annee_str = f"en {result.annee}" if result.annee else "sur toute la période"
    return (
        f"À {result.ville} ({type_str}, {annee_str}) : "
        f"prix médian {result.prix_median_m2:,.0f} €/m², "
        f"prix moyen {result.prix_moyen_m2:,.0f} €/m², "
        f"fourchette habituelle {result.prix_min_m2:,.0f}–{result.prix_max_m2:,.0f} €/m², "
        f"{result.volume_transactions} transactions."
    )
