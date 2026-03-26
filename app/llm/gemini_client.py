import json
import os
from google import genai
from google.genai import types
from app.models.schemas import Intent, IntentType, TypeLocal


_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


MODEL = "gemini-2.5-flash"


INTENT_SYSTEM_PROMPT = """Tu es un assistant spécialisé dans l'analyse de questions immobilières françaises.
Tu dois extraire l'intention et les paramètres d'une question utilisateur.

Intentions possibles :
- prix_m2 : connaître le prix au m² d'un lieu
- comparables : trouver des transactions similaires
- estimation : estimer la valeur d'un bien
- evolution : voir l'évolution des prix dans le temps
- comparaison : comparer deux zones/villes/départements
- unknown : question non reconnue

Types de biens : "Appartement" ou "Maison" uniquement.

Pour les comparaisons par département, utilise departement et departement_comparaison (codes 2 chiffres).
Pour les comparaisons par ville, utilise ville et ville_comparaison.

Exemples :
"prix m2 Lyon appartement" → type=prix_m2, ville=Lyon, type_local=Appartement
"estimation maison 90m2 Bordeaux" → type=estimation, ville=Bordeaux, type_local=Maison, surface=90
"comparaison Lyon vs Paris" → type=comparaison, ville=Lyon, ville_comparaison=Paris
"comparer le 75 et le 69" → type=comparaison, departement=75, departement_comparaison=69
"évolution des prix à Marseille" → type=evolution, ville=Marseille
"""

RESPONSE_SYSTEM_PROMPT = """Tu es DVF GPT, un assistant immobilier expert utilisant les données officielles DVF françaises.
Tu reformules les résultats d'analyse de données en réponses naturelles, claires et professionnelles en français.
Sois concis, précis et utile. Mets en valeur les chiffres clés avec du **gras**.
Ne dis jamais que tu "analyses" les données - tu présentes des résultats déjà calculés.
Utilise des émojis avec parcimonie pour structurer la réponse.
Utilise le format Markdown : **gras** pour les chiffres importants, listes à puces si pertinent.
Réponds en 3-5 phrases maximum.
"""


def parse_intent(question: str) -> Intent:
    """Extract structured intent from user question using Gemini with enforced JSON schema."""
    client = get_client()

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=f"Question : {question}",
            config=types.GenerateContentConfig(
                system_instruction=INTENT_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=Intent,
            ),
        )
        text = response.text.strip()
        data = json.loads(text)
        return Intent(**data)
    except Exception as e:
        print(f"Intent parsing error: {e}")
        return Intent(type=IntentType.UNKNOWN, confidence=0.0)


def generate_response(question: str, result_summary: str) -> str:
    """Generate natural language response from analysis results."""
    client = get_client()
    prompt = f"""{RESPONSE_SYSTEM_PROMPT}

Question de l'utilisateur : {question}

Résultats de l'analyse :
{result_summary}

Génère une réponse naturelle et professionnelle en français."""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Response generation error: {e}")
        return result_summary
