from app.llm import gemini_client
from app.models.schemas import Intent


def extract_intent(question: str) -> Intent:
    """Extract structured intent from user question."""
    return gemini_client.parse_intent(question)
