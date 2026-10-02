import re

from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Response, jsonify, redirect, render_template, request, url_for

from app.services.screening_service import (
    get_recommendations,
    get_screening_summary,
    get_strategy_rows,
    refresh_market_data,
)


def register_routes(app):
    @app.route("/robots.txt")
    def robots_txt():
        sitemap_url = url_for("sitemap_xml", _external=True, _scheme="https")
        content = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /market-data/refresh\n"
            f"Sitemap: {sitemap_url}\n"
        )
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        sitemap = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for endpoint in ("dashboard", "recommendations_page"):
            entry = SubElement(sitemap, "url")
            SubElement(entry, "loc").text = url_for(endpoint, _external=True, _scheme="https")
        return Response(
            tostring(sitemap, encoding="utf-8", xml_declaration=True),
            mimetype="application/xml",
        )

    @app.route("/")
    def dashboard():
        overview = get_screening_summary()
        recommendation_data = get_recommendations()
        return render_template(
            "dashboard.html",
            overview=overview,
            recommendations=recommendation_data["recommendations"],
            fixed_allocation=recommendation_data["fixed_allocation"],
            refresh_result=request.args.get("refresh_result"),
        )

    @app.route("/dashboard")
    def dashboard_alias():
        return redirect(url_for("dashboard"))

    @app.route("/recommendations")
    def recommendations_page():
        requested_symbol = request.args.get("symbol", "").strip().upper()
        if requested_symbol and not re.fullmatch(r"[A-Z0-9]{1,10}", requested_symbol):
            return "Mã cổ phiếu không hợp lệ.", 400
        symbols = [requested_symbol] if requested_symbol else None
        recommendation_data = get_recommendations(symbols=symbols)
        overview = get_screening_summary(symbols=symbols)
        return render_template(
            "recommendations.html",
            recommendations=recommendation_data["recommendations"],
            requested_symbol=requested_symbol,
            fixed_allocation=recommendation_data["fixed_allocation"],
            data_source=overview["source"],
            data_status=overview["data_status"],
            cache_status=overview["cache_status"],
            data_updated_at=overview["data_updated_at"],
            priced_count=overview["priced_count"],
            universe_count=overview["universe_count"],
            refresh_result=request.args.get("refresh_result"),
        )

    @app.route("/market-data/refresh", methods=["POST"])
    def refresh_market_data_route():
        requested_symbol = request.form.get("symbol", "").strip().upper()
        if requested_symbol and not re.fullmatch(r"[A-Z0-9]{1,10}", requested_symbol):
            return "Mã cổ phiếu không hợp lệ.", 400
        symbols = [requested_symbol] if requested_symbol else None
        refresh_market_data(symbols=symbols)
        overview = get_screening_summary(symbols=symbols)
        refresh_result = (
            "success"
            if overview["cache_status"] in {"live", "demo"}
            else "stale" if overview["cache_status"] == "stale" else "unavailable"
        )
        return_to = request.form.get("return_to")
        endpoint = return_to if return_to in {"dashboard", "recommendations_page"} else "dashboard"
        return redirect(
            url_for(
                endpoint,
                refresh_result=refresh_result,
                **({"symbol": requested_symbol} if requested_symbol and endpoint == "recommendations_page" else {}),
            )
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
