from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import requests
import os

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("QUICKCOMMERCE_API_KEY", "")

API_BASE_URL = "https://api.quickcommerceapi.com"

LATITUDE = float(os.getenv("PRICEWISE_LAT", "15.8281"))
LONGITUDE = float(os.getenv("PRICEWISE_LON", "78.0373"))

PLATFORMS = [
    "Amazon",
    "Flipkart",
    "Myntra"
]

API_HEADERS = {
    "X-API-Key": API_KEY
}


def search_platform(query, platform):
    """
    Search one marketplace using QuickCommerce API.
    """

    if not API_KEY:
        return {
            "store": platform,
            "products": [],
            "error": "API key is missing. Configure your .env file."
        }

    params = {
        "q": query,
        "lat": LATITUDE,
        "lon": LONGITUDE,
        "platform": platform
    }

    try:
        response = requests.get(
            f"{API_BASE_URL}/v1/search",
            headers=API_HEADERS,
            params=params,
            timeout=25
        )

        response.raise_for_status()
        payload = response.json()

        if payload.get("status") not in (None, "success"):
            return {
                "store": platform,
                "products": [],
                "error": payload.get(
                    "message",
                    "Marketplace search failed."
                )
            }

        data = payload.get("data", payload)

        # The documented API returns products inside data.products.
        products = data.get(
            "products",
            data.get("results", [])
        )

        normalized_products = []

        for product in products:
            price = product.get("offer_price")

            if price is None:
                price = product.get("price")

            images = product.get("images", [])

            image_url = (
                images[0]
                if isinstance(images, list) and images
                else product.get("image")
            )

            platform_data = product.get("platform", {})

            if isinstance(platform_data, dict):
                store_name = platform_data.get("name", platform)
            else:
                store_name = platform

            normalized_products.append({
                "store": store_name,
                "name": product.get("name", "Product"),
                "brand": product.get("brand"),
                "price": price,
                "mrp": product.get("mrp"),
                "quantity": product.get(
                    "quantity",
                    product.get("weight", "")
                ),
                "available": product.get(
                    "available",
                    product.get("in_stock", True)
                ),
                "image": image_url,
                "url": product.get(
                    "deeplink",
                    product.get("url", "")
                ),
                "rating": product.get("rating"),
                "rating_count": product.get("rating_count"),
                "item_id": product.get(
                    "id",
                    product.get("item_id", "")
                )
            })

        return {
            "store": platform,
            "products": normalized_products,
            "error": None
        }

    except requests.exceptions.Timeout:
        return {
            "store": platform,
            "products": [],
            "error": "Marketplace request timed out."
        }

    except requests.exceptions.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else None
        )

        if status_code == 401:
            message = "API key is invalid or unauthorized."
        elif status_code == 402:
            message = "API credits or payment may be required."
        elif status_code == 429:
            message = "API rate limit reached."
        else:
            message = f"Marketplace API error: HTTP {status_code}"

        return {
            "store": platform,
            "products": [],
            "error": message
        }

    except (requests.exceptions.RequestException, ValueError):
        return {
            "store": platform,
            "products": [],
            "error": "Unable to retrieve marketplace data."
        }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search_products():
    data = request.get_json(silent=True) or {}

    query = str(data.get("query", "")).strip()

    if not query:
        return jsonify({
            "error": "Enter a product name."
        }), 400

    if len(query) > 150:
        return jsonify({
            "error": "Product search must be 150 characters or fewer."
        }), 400

    if not API_KEY:
        return jsonify({
            "error": (
                "QuickCommerce API key is missing. "
                "Add your key to the .env file and restart the server."
            )
        }), 503

    # Search the marketplaces concurrently.
    with ThreadPoolExecutor(max_workers=3) as executor:
        marketplace_results = list(
            executor.map(
                lambda platform: search_platform(query, platform),
                PLATFORMS
            )
        )

    products = []
    errors = []

    for result in marketplace_results:
        products.extend(result["products"])

        if result["error"]:
            errors.append({
                "store": result["store"],
                "message": result["error"]
            })

    # Sort available products by price, lowest first.
    def price_sort_key(product):
        price = product.get("price")

        try:
            if price is None:
                return (1, float("inf"))

            return (0, float(price))

        except (TypeError, ValueError):
            return (1, float("inf"))

    products.sort(key=price_sort_key)

    cheapest = next(
        (
            product for product in products
            if product.get("available")
            and product.get("price") is not None
        ),
        None
    )

    return jsonify({
        "query": query,
        "results": products,
        "cheapest": cheapest,
        "errors": errors,
        "location": {
            "latitude": LATITUDE,
            "longitude": LONGITUDE
        },
        "message": (
            "Live API results retrieved."
            if products
            else "No matching products were returned."
        )
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_configured": bool(API_KEY)
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )