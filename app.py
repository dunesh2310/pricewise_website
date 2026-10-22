from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import requests
import os
import logging
import math
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
API_KEY = os.getenv("QUICKCOMMERCE_API_KEY", "").strip()
API_BASE_URL = "https://api.quickcommerceapi.com"
LATITUDE = float(os.getenv("PRICEWISE_LAT", "15.8281"))
LONGITUDE = float(os.getenv("PRICEWISE_LON", "78.0373"))
PLATFORMS = ["Amazon", "Flipkart", "Myntra"]
API_HEADERS = {
    "X-API-Key": API_KEY,
    "Accept": "application/json"
}
def normalize_product(product, requested_platform):
    """Convert an API product into PriceWise's standard format."""
    if not isinstance(product, dict):
        return None
    raw_price = product.get("offer_price")
    if raw_price is None:
        raw_price = product.get("price")
    try:
        price = float(raw_price) if raw_price is not None else None
        if price is not None and (
            not math.isfinite(price) or price < 0
        ):
            price = None
    except (TypeError, ValueError):
        price = None
    raw_mrp = product.get("mrp")
    try:
        mrp = float(raw_mrp) if raw_mrp is not None else None
        if mrp is not None and not math.isfinite(mrp):
            mrp = None
    except (TypeError, ValueError):
        mrp = None
    images = product.get("images", [])
    if isinstance(images, list):
        image_url = images[0] if images else product.get("image")
    elif isinstance(images, str):
        image_url = images
    else:
        image_url = product.get("image")
    platform_data = product.get("platform", {})
    if isinstance(platform_data, dict):
        store_name = platform_data.get("name", requested_platform)
    elif isinstance(platform_data, str):
        store_name = platform_data
    else:
        store_name = requested_platform
    available = product.get(
        "available",
        product.get("in_stock", True)
    )
    return {
        "store": store_name,
        "name": product.get("name") or product.get("title") or "Product",
        "brand": product.get("brand"),
        "price": price,
        "mrp": mrp,
        "quantity": product.get(
            "quantity",
            product.get("weight", "")
        ),
        "available": available is not False,
        "image": image_url,
        "url": product.get("deeplink") or product.get("url") or "",
        "rating": product.get("rating"),
        "rating_count": product.get("rating_count"),
        "item_id": product.get("id") or product.get("item_id") or ""
    }
def search_platform(query, platform):
    """Search one marketplace through QuickCommerce."""
    if not API_KEY:
        return {
            "store": platform,
            "products": [],
            "error": "API key is missing."
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
            timeout=30
        )
        if not response.ok:
            status = response.status_code
            # Log diagnostic details without logging the API key.
            logging.warning(
                "QuickCommerce returned HTTP %s for %s: %s",
                status,
                platform,
                response.text[:500]
            )
            if status == 401:
                message = (
                    "API authorization failed. Check the key and "
                    "the authentication method used by this request."
                )
            elif status == 402:
                message = "API credits or payment may be required."
            elif status == 403:
                message = "Access to this request is restricted."
            elif status == 422:
                message = "The API rejected the search parameters."
            elif status == 429:
                message = "API rate limit reached. Try again later."
            else:
                message = f"QuickCommerce API returned HTTP {status}."
            return {
                "store": platform,
                "products": [],
                "error": message
            }
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
        if not isinstance(data, dict):
            return {
                "store": platform,
                "products": [],
                "error": "Unexpected API response format."
            }
        raw_products = data.get(
            "products",
            data.get("results", [])
        )
        if not isinstance(raw_products, list):
            raw_products = []
        products = []
        for item in raw_products:
            normalized = normalize_product(item, platform)
            if normalized:
                products.append(normalized)
        logging.info(
            "QuickCommerce: %s returned %s products for query %r",
            platform,
            len(products),
            query
        )
        return {
            "store": platform,
            "products": products,
            "error": None
        }
    except requests.exceptions.Timeout:
        return {
            "store": platform,
            "products": [],
            "error": "Marketplace request timed out."
        }
    except requests.exceptions.RequestException:
        logging.exception("Network error while searching %s", platform)
        return {
            "store": platform,
            "products": [],
            "error": "Unable to connect to the marketplace API."
        }
    except ValueError:
        logging.exception("Invalid JSON returned by %s", platform)
        return {
            "store": platform,
            "products": [],
            "error": "The marketplace API returned invalid JSON."
        }
@app.route("/")
def home():
    return render_template("index.html")
@app.route("/api/search", methods=["POST"])
def search_products():
    data = request.get_json(silent=True) or {}
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"error": "Enter a product name."}), 400
    if len(query) > 150:
        return jsonify({
            "error": "Product search must be 150 characters or fewer."
        }), 400
    if not API_KEY:
        return jsonify({
            "error": (
                "QuickCommerce API key is missing. Configure "
                "QUICKCOMMERCE_API_KEY in your environment."
            )
        }), 503
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
    # Put valid prices first, sorted from lowest to highest.
    products.sort(
        key=lambda p: (
            p["price"] is None,
            p["price"] if p["price"] is not None else float("inf")
        )
    )
    cheapest = next(
        (
            product for product in products
            if product["available"] and product["price"] is not None
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