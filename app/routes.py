from flask import jsonify, render_template

from app.services.screening_service import (
    get_recommendations,
    get_screening_summary,
    get_strategy_rows,
)


def register_routes(app):
    @app.route("/")
    def dashboard():
        overview = get_screening_summary()
        recommendation_data = get_recommendations()
        return render_template(
            "dashboard.html",
            overview=overview,
            recommendations=recommendation_data["recommendations"],
            fixed_allocation=recommendation_data["fixed_allocation"],
        )

    @app.route("/recommendations")
    def recommendations_page():
        recommendation_data = get_recommendations()
        return render_template(
            "recommendations.html",
            recommendations=recommendation_data["recommendations"],
            fixed_allocation=recommendation_data["fixed_allocation"],
        )

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "services": {"screening": "ok"}})

    @app.route("/api/overview")
    def overview():
        return jsonify(get_screening_summary())

    @app.route("/api/recommendations")
    def api_recommendations():
        return jsonify(get_recommendations())

    @app.route("/api/strategy/<strategy>")
    def strategy(strategy):
        rows = get_strategy_rows(strategy)
        return jsonify({"strategy": strategy, "rows": rows, "metrics": {"count": len(rows)}})
