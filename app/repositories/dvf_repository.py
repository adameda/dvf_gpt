import duckdb
import os
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/dvf.duckdb")

# Villes dont les arrondissements doivent être agrégés
_VILLES_ARRONDISSEMENTS = {"paris", "lyon", "marseille"}


def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


def _ville_condition(col: str, ville: str) -> str:
    """Build SQL condition that matches a city name including its arrondissements."""
    return f"(LOWER({col}) = LOWER(?) OR LOWER({col}) LIKE LOWER(? || ' %'))"


def _is_ville_arrondissements(ville: str) -> bool:
    return ville.lower() in _VILLES_ARRONDISSEMENTS


def fetch_prix_m2(
    ville: Optional[str] = None,
    departement: Optional[str] = None,
    type_local: Optional[str] = None,
    annee: Optional[int] = None,
) -> list[dict]:
    """Fetch prix m² statistics for a location, aggregating arrondissements."""
    conditions = []
    params = []
    aggregate_ville = False

    if ville:
        conditions.append(_ville_condition("nom_commune", ville))
        params.extend([ville, ville])
        aggregate_ville = _is_ville_arrondissements(ville)
    if departement:
        conditions.append("code_departement = ?")
        params.append(str(departement))
    if type_local:
        conditions.append("type_local = ?")
        params.append(type_local)
    if annee:
        conditions.append("annee_mutation = ?")
        params.append(annee)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    if aggregate_ville and ville:
        # Aggregate all arrondissements into one result per type_local
        sql = f"""
            SELECT
                ? AS nom_commune,
                type_local,
                ROUND(MEDIAN(prix_m2), 0)      AS prix_median_m2,
                ROUND(AVG(prix_m2), 0)         AS prix_moyen_m2,
                COUNT(*)                        AS volume_transactions,
                ROUND(PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY prix_m2), 0) AS prix_min_m2,
                ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY prix_m2), 0) AS prix_max_m2,
                MAX(annee_mutation)             AS annee,
                ROUND(AVG(latitude), 6)        AS latitude,
                ROUND(AVG(longitude), 6)       AS longitude
            FROM transactions_clean
            {where}
            GROUP BY type_local
            ORDER BY volume_transactions DESC
        """
        all_params = [ville.title()] + params
    else:
        sql = f"""
            SELECT
                nom_commune,
                type_local,
                ROUND(MEDIAN(prix_m2), 0)      AS prix_median_m2,
                ROUND(AVG(prix_m2), 0)         AS prix_moyen_m2,
                COUNT(*)                        AS volume_transactions,
                ROUND(PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY prix_m2), 0) AS prix_min_m2,
                ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY prix_m2), 0) AS prix_max_m2,
                MAX(annee_mutation)             AS annee,
                ROUND(AVG(latitude), 6)        AS latitude,
                ROUND(AVG(longitude), 6)       AS longitude
            FROM transactions_clean
            {where}
            GROUP BY nom_commune, type_local
            ORDER BY volume_transactions DESC
            LIMIT 10
        """
        all_params = params

    with get_connection() as con:
        return con.execute(sql, all_params).fetchdf().to_dict("records")


def fetch_comparables(
    ville: str,
    type_local: str,
    surface: float,
    limit: int = 20,
) -> list[dict]:
    """Fetch comparable transactions (same city, type, surface ±20%)."""
    surface_min = surface * 0.80
    surface_max = surface * 1.20

    sql = """
        SELECT
            id_mutation,
            CAST(date_mutation AS VARCHAR) AS date_mutation,
            valeur_fonciere,
            surface_reelle_bati,
            nombre_pieces_principales,
            nom_commune,
            type_local,
            latitude,
            longitude,
            ROUND(prix_m2, 0) AS prix_m2
        FROM transactions_clean
        WHERE (LOWER(nom_commune) = LOWER(?) OR LOWER(nom_commune) LIKE LOWER(? || ' %'))
          AND type_local = ?
          AND surface_reelle_bati BETWEEN ? AND ?
          AND annee_mutation >= 2023
        ORDER BY date_mutation DESC
        LIMIT ?
    """
    with get_connection() as con:
        return con.execute(sql, [ville, ville, type_local, surface_min, surface_max, limit]).fetchdf().to_dict("records")


def fetch_evolution(
    ville: Optional[str] = None,
    departement: Optional[str] = None,
    type_local: Optional[str] = None,
) -> list[dict]:
    """Fetch yearly price evolution."""
    conditions = []
    params = []

    if ville:
        conditions.append("(LOWER(nom_commune) = LOWER(?) OR LOWER(nom_commune) LIKE LOWER(? || ' %'))")
        params.extend([ville, ville])
    if departement:
        conditions.append("code_departement = ?")
        params.append(str(departement))
    if type_local:
        conditions.append("type_local = ?")
        params.append(type_local)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = f"""
        SELECT
            annee_mutation                  AS annee,
            ROUND(MEDIAN(prix_m2), 0)      AS prix_median_m2,
            COUNT(*)                        AS volume_transactions
        FROM transactions_clean
        {where}
        GROUP BY annee_mutation
        ORDER BY annee_mutation
    """
    with get_connection() as con:
        return con.execute(sql, params).fetchdf().to_dict("records")


def fetch_comparaison(
    ville_a: str,
    ville_b: str,
    type_local: Optional[str] = None,
) -> list[dict]:
    """Fetch comparison data between two cities, aggregating arrondissements."""
    type_filter = "AND type_local = ?" if type_local else ""

    # Build each city as a subquery that aggregates arrondissements
    sql = f"""
        SELECT
            ? AS zone,
            type_local,
            ROUND(MEDIAN(prix_m2), 0)      AS prix_median_m2,
            COUNT(*)                        AS volume_transactions
        FROM transactions_clean
        WHERE {_ville_condition("nom_commune", ville_a)}
        {type_filter}
        GROUP BY type_local

        UNION ALL

        SELECT
            ? AS zone,
            type_local,
            ROUND(MEDIAN(prix_m2), 0)      AS prix_median_m2,
            COUNT(*)                        AS volume_transactions
        FROM transactions_clean
        WHERE {_ville_condition("nom_commune", ville_b)}
        {type_filter}
        GROUP BY type_local

        ORDER BY prix_median_m2 DESC
    """
    params_a = [ville_a.title(), ville_a, ville_a] + ([type_local] if type_local else [])
    params_b = [ville_b.title(), ville_b, ville_b] + ([type_local] if type_local else [])
    params = params_a + params_b

    with get_connection() as con:
        return con.execute(sql, params).fetchdf().to_dict("records")


def search_commune(query: str) -> list[dict]:
    """Search communes by name (fuzzy)."""
    sql = """
        SELECT DISTINCT nom_commune, code_departement
        FROM transactions_clean
        WHERE LOWER(nom_commune) LIKE LOWER(?)
        ORDER BY nom_commune
        LIMIT 5
    """
    with get_connection() as con:
        return con.execute(sql, [f"%{query}%"]).fetchdf().to_dict("records")


def fetch_comparaison_departement(
    dept_a: str,
    dept_b: str,
    type_local: Optional[str] = None,
) -> list[dict]:
    """Fetch comparison data between two départements."""
    type_filter = "AND type_local = ?" if type_local else ""

    sql = f"""
        SELECT
            ? AS zone,
            type_local,
            ROUND(MEDIAN(prix_m2), 0) AS prix_median_m2,
            COUNT(*) AS volume_transactions
        FROM transactions_clean
        WHERE code_departement = ?
        {type_filter}
        GROUP BY type_local

        UNION ALL

        SELECT
            ? AS zone,
            type_local,
            ROUND(MEDIAN(prix_m2), 0) AS prix_median_m2,
            COUNT(*) AS volume_transactions
        FROM transactions_clean
        WHERE code_departement = ?
        {type_filter}
        GROUP BY type_local

        ORDER BY prix_median_m2 DESC
    """
    params_a = [f"Département {dept_a}", str(dept_a)] + ([type_local] if type_local else [])
    params_b = [f"Département {dept_b}", str(dept_b)] + ([type_local] if type_local else [])

    with get_connection() as con:
        return con.execute(sql, params_a + params_b).fetchdf().to_dict("records")


def db_exists() -> bool:
    return os.path.exists(DB_PATH)
