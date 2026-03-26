from app.repositories import dvf_repository
from app.models.schemas import ComparaisonResult, ComparaisonZone, Intent
from typing import Optional


def _build_zone(row) -> ComparaisonZone:
    return ComparaisonZone(
        zone=str(row["zone"]),
        type_local=row.get("type_local"),
        prix_median_m2=float(row["prix_median_m2"]),
        volume_transactions=int(row["volume_transactions"]),
    )


def _pick_and_build(rows: list[dict], zone_key: str) -> Optional[ComparaisonZone]:
    """Pick the row with the most transactions for a given zone."""
    zone_rows = [r for r in rows if r["zone"].lower() == zone_key.lower()]
    if not zone_rows:
        return None
    best = max(zone_rows, key=lambda r: r["volume_transactions"])
    return _build_zone(best)


def _build_result(zone_a: ComparaisonZone, zone_b: ComparaisonZone) -> ComparaisonResult:
    if zone_b.prix_median_m2 > 0:
        diff_pct = ((zone_a.prix_median_m2 - zone_b.prix_median_m2) / zone_b.prix_median_m2) * 100
    else:
        diff_pct = 0.0
    return ComparaisonResult(zone_a=zone_a, zone_b=zone_b, difference_pct=round(diff_pct, 1))


def get_comparaison(intent: Intent) -> Optional[ComparaisonResult]:
    """Compare two zones (cities or départements)."""

    # --- Comparison by département ---
    if intent.departement and intent.departement_comparaison:
        rows = dvf_repository.fetch_comparaison_departement(
            dept_a=intent.departement,
            dept_b=intent.departement_comparaison,
            type_local=intent.type_local.value if intent.type_local else None,
        )
        if not rows or len(rows) < 2:
            return None

        zone_a = _pick_and_build(rows, f"Département {intent.departement}")
        zone_b = _pick_and_build(rows, f"Département {intent.departement_comparaison}")
        if not zone_a or not zone_b:
            return None
        return _build_result(zone_a, zone_b)

    # --- Comparison by ville ---
    if not intent.ville or not intent.ville_comparaison:
        return None

    rows = dvf_repository.fetch_comparaison(
        ville_a=intent.ville,
        ville_b=intent.ville_comparaison,
        type_local=intent.type_local.value if intent.type_local else None,
    )

    if not rows or len(rows) < 2:
        return None

    zone_a = _pick_and_build(rows, intent.ville)
    zone_b = _pick_and_build(rows, intent.ville_comparaison)
    if not zone_a or not zone_b:
        return None
    return _build_result(zone_a, zone_b)


def format_summary(result: ComparaisonResult) -> str:
    direction = "plus cher" if result.difference_pct > 0 else "moins cher"
    return (
        f"Comparaison {result.zone_a.zone} vs {result.zone_b.zone} : "
        f"{result.zone_a.zone} à {result.zone_a.prix_median_m2:,.0f} €/m² "
        f"({result.zone_a.volume_transactions} transactions), "
        f"{result.zone_b.zone} à {result.zone_b.prix_median_m2:,.0f} €/m² "
        f"({result.zone_b.volume_transactions} transactions). "
        f"{result.zone_a.zone} est {abs(result.difference_pct):.1f}% {direction} que {result.zone_b.zone}."
    )
