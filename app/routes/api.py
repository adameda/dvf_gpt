from flask import Blueprint, request, jsonify
from app.services import chat_service
from app.repositories import dvf_repository

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' field"}), 400

    question = data["message"].strip()
    if not question:
        return jsonify({"error": "Empty message"}), 400

    try:
        response = chat_service.handle_message(question)
        return jsonify(response.model_dump())
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({
            "intent": "unknown",
            "message": "Une erreur s'est produite. Veuillez réessayer.",
            "data_type": "error",
            "data": None,
            "visualisation": None,
        }), 500


@api_bp.route("/health", methods=["GET"])
def health():
    db_ok = dvf_repository.db_exists()
    return jsonify({
        "status": "ok",
        "database": "ready" if db_ok else "missing",
    })
