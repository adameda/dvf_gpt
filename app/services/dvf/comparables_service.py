from app.repositories import dvf_repository
from app.models.schemas import ComparablesResult, ComparableTransaction, Intent
from typing import Optional
import statistics


def get_comparables(intent: Intent) -> Optional[ComparablesResult]:
    """Get comparable transactions for a property."""
    if not intent.ville or not intent.surface:
        return None

    type_local = intent.type_local.value if intent.type_local else "Appartement"

    rows = dvf_repository.fetch_comparables(
        ville=intent.ville,
        type_local=type_local,
        surface=intent.surface,
    )

    if not rows:
        return None

    transactions = []
    for row in rows:
        transactions.append(ComparableTransaction(
            id_mutation=str(row["id_mutation"]),
            date_mutation=str(row["date_mutation"]),
            valeur_fonciere=float(row["valeur_fonciere"]),
            surface_reelle_bati=float(row["surface_reelle_bati"]),
            nombre_pieces_principales=int(row["nombre_pieces_principales"]) if row.get("nombre_pieces_principales") else None,
            nom_commune=str(row["nom_commune"]),
            type_local=str(row["type_local"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            prix_m2=float(row["prix_m2"]),
        ))

    prix_list = [t.prix_m2 for t in transactions]
    prix_median = statistics.median(prix_list) if prix_list else 0

    return ComparablesResult(
        ville=intent.ville,
        type_local=type_local,
        surface=intent.surface,
        transactions=transactions,
        prix_median_m2=round(prix_median, 0),
        count=len(transactions),
    )


def format_summary(result: ComparablesResult) -> str:
    return (
        f"{result.count} comparables trouvés pour un {result.type_local.lower()} "
        f"de {result.surface}m² à {result.ville}. "
        f"Prix médian au m² parmi les comparables : {result.prix_median_m2:,.0f} €/m²."
    )
