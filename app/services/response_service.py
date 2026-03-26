from app.llm import gemini_client


def generate_natural_response(question: str, summary: str) -> str:
    """Generate a natural language response using LLM."""
    return gemini_client.generate_response(question, summary)
