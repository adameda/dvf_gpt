from app.models.schemas import ChatResponse, IntentType
from app.services import intent_service, response_service
from app.services.dvf import (
    price_service,
    comparables_service,
    estimation_service,
    trend_service,
    comparison_service,
)
from app.repositories import dvf_repository


def handle_message(question: str) -> ChatResponse:
    """Main pipeline: question → intent → data → LLM response → structured output."""

    # Check database
    if not dvf_repository.db_exists():
        return ChatResponse(
            intent=IntentType.UNKNOWN,
            message="⚠️ La base de données DVF n'est pas encore disponible. Lancez le script `build_dvf_database.py`.",
            data_type="error",
        )

    # Step 1: Extract intent via LLM
    intent = intent_service.extract_intent(question)

    # Build debug info
    debug_info = {
        "intent_parsed": intent.model_dump(),
        "steps": [f"1. Intent détecté : **{intent.type.value}** (confiance : {intent.confidence})"],
    }
    if intent.ville:
        debug_info["steps"].append(f"2. Ville ciblée : **{intent.ville}**")
    if intent.departement:
        debug_info["steps"].append(f"2. Département ciblé : **{intent.departement}**")
    if intent.type_local:
        debug_info["steps"].append(f"3. Type de bien : **{intent.type_local.value}**")
    if intent.surface:
        debug_info["steps"].append(f"4. Surface : **{intent.surface} m²**")

    # Step 2: Route to appropriate service
    if intent.type == IntentType.PRIX_M2:
        return _handle_prix_m2(question, intent, debug_info)

    elif intent.type == IntentType.COMPARABLES:
        return _handle_comparables(question, intent, debug_info)

    elif intent.type == IntentType.ESTIMATION:
        return _handle_estimation(question, intent, debug_info)

    elif intent.type == IntentType.EVOLUTION:
        return _handle_evolution(question, intent, debug_info)

    elif intent.type == IntentType.COMPARAISON:
        return _handle_comparaison(question, intent, debug_info)

    else:
        return ChatResponse(
            intent=IntentType.UNKNOWN,
            message="Je n'ai pas compris votre question. Essayez une formulation différente !",
            data_type="unknown",
            debug=debug_info,
        )


def _handle_prix_m2(question: str, intent, debug_info: dict) -> ChatResponse:
    if not intent.ville and not intent.departement:
        return _missing_location()

    result = price_service.get_prix_m2(intent)
    if not result:
        return _no_data(intent.ville or intent.departement)

    summary = price_service.format_summary(result)
    debug_info["steps"].append(f"5. Requête SQL → **{result.volume_transactions}** transactions trouvées")
    debug_info["steps"].append(f"6. Prix médian calculé : **{result.prix_median_m2:,.0f} €/m²**")
    debug_info["summary"] = summary
    message = response_service.generate_natural_response(question, summary)

    return ChatResponse(
        intent=IntentType.PRIX_M2,
        message=message,
        data_type="prix_m2",
        data=result.model_dump(),
        visualisation="map",
        debug=debug_info,
    )


def _handle_comparables(question: str, intent, debug_info: dict) -> ChatResponse:
    if not intent.ville:
        return _missing_location()
    if not intent.surface:
        return ChatResponse(
            intent=IntentType.COMPARABLES,
            message="Précisez la surface du bien (ex : « comparables appartement 70m² Lyon »).",
            data_type="error",
        )

    result = comparables_service.get_comparables(intent)
    if not result or result.count == 0:
        return _no_data(intent.ville)

    summary = comparables_service.format_summary(result)
    debug_info["steps"].append(f"5. Recherche comparables ±20% autour de **{intent.surface} m²**")
    debug_info["steps"].append(f"6. **{result.count}** transactions comparables trouvées")
    debug_info["summary"] = summary
    message = response_service.generate_natural_response(question, summary)

    return ChatResponse(
        intent=IntentType.COMPARABLES,
        message=message,
        data_type="comparables",
        data=result.model_dump(),
        visualisation="map_comparables",
        debug=debug_info,
    )


def _handle_estimation(question: str, intent, debug_info: dict) -> ChatResponse:
    if not intent.ville:
        return _missing_location()
    if not intent.surface:
        return ChatResponse(
            intent=IntentType.ESTIMATION,
            message="Précisez la surface du bien (ex : « estimation appartement 80m² Marseille »).",
            data_type="error",
        )

    result = estimation_service.get_estimation(intent)
    if not result:
        return _no_data(intent.ville)

    summary = estimation_service.format_summary(result)
    debug_info["steps"].append(f"5. **{result.nb_comparables}** comparables → médiane **{result.prix_median_m2:,.0f} €/m²**")
    debug_info["steps"].append(f"6. Estimation : **{result.estimation_basse:,.0f}** – **{result.estimation_haute:,.0f} €**")
    debug_info["summary"] = summary
    message = response_service.generate_natural_response(question, summary)

    return ChatResponse(
        intent=IntentType.ESTIMATION,
        message=message,
        data_type="estimation",
        data=result.model_dump(),
        visualisation="map_comparables",
        debug=debug_info,
    )


def _handle_evolution(question: str, intent, debug_info: dict) -> ChatResponse:
    if not intent.ville and not intent.departement:
        return _missing_location()

    result = trend_service.get_evolution(intent)
    if not result or not result.evolution:
        return _no_data(intent.ville or intent.departement)

    summary = trend_service.format_summary(result)
    years = [str(e.annee) for e in result.evolution]
    debug_info["steps"].append(f"5. Données sur **{len(result.evolution)}** années : {', '.join(years)}")
    debug_info["summary"] = summary
    message = response_service.generate_natural_response(question, summary)

    return ChatResponse(
        intent=IntentType.EVOLUTION,
        message=message,
        data_type="evolution",
        data=result.model_dump(),
        visualisation="chart_line",
        debug=debug_info,
    )


def _handle_comparaison(question: str, intent, debug_info: dict) -> ChatResponse:
    has_villes = intent.ville and intent.ville_comparaison
    has_depts = intent.departement and intent.departement_comparaison
    if not has_villes and not has_depts:
        return ChatResponse(
            intent=IntentType.COMPARAISON,
            message="Précisez les deux zones à comparer (ex : « comparer Lyon et Marseille » ou « comparer le 75 et le 69 »).",
            data_type="error",
        )

    result = comparison_service.get_comparaison(intent)
    if not result:
        label = f"{intent.ville} / {intent.ville_comparaison}" if has_villes else f"Dép. {intent.departement} / Dép. {intent.departement_comparaison}"
        return _no_data(label)

    summary = comparison_service.format_summary(result)
    debug_info["steps"].append(f"5. Comparaison **{result.zone_a.zone}** vs **{result.zone_b.zone}**")
    debug_info["steps"].append(f"6. Écart : **{result.difference_pct:+.1f}%**")
    debug_info["summary"] = summary
    message = response_service.generate_natural_response(question, summary)

    return ChatResponse(
        intent=IntentType.COMPARAISON,
        message=message,
        data_type="comparaison",
        data=result.model_dump(),
        visualisation="chart_bar",
        debug=debug_info,
    )


def _missing_location() -> ChatResponse:
    return ChatResponse(
        intent=IntentType.UNKNOWN,
        message="Précisez une **ville** ou un **département** pour que je puisse vous répondre.\n\n"
               "Exemples :\n"
               "• « prix m² à Lyon »\n"
               "• « prix m² dans le 75 »\n"
               "• « évolution des prix dans le 33 »",
        data_type="error",
    )


def _no_data(location: str) -> ChatResponse:
    return ChatResponse(
        intent=IntentType.UNKNOWN,
        message=f"Aucune donnée disponible pour « {location} » dans la base DVF. Vérifiez l'orthographe ou essayez une autre ville.",
        data_type="error",
    )
