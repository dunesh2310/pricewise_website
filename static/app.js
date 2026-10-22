document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("searchForm");
    const productInput = document.getElementById("productInput");
    const searchButton = document.getElementById("searchButton");
    const resultsSection = document.getElementById("resultsSection");
    const resultsGrid = document.getElementById("resultsGrid");
    const resultMessage = document.getElementById("resultMessage");
    if (!searchForm || !productInput || !resultsGrid) {
        console.error("PriceWise: Required HTML elements are missing.");
        return;
    }
    searchForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const query = productInput.value.trim();
        if (!query) {
            alert("Please enter a product name.");
            return;
        }
        if (searchButton) {
            searchButton.disabled = true;
            searchButton.textContent = "Searching...";
        }
        resultsGrid.innerHTML = "";
        if (resultsSection) resultsSection.style.display = "block";
        if (resultMessage) resultMessage.textContent = "Searching for products...";
        try {
            const response = await fetch("/api/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ query })
            });
            const data = await response.json();
            console.log("PriceWise API response:", data);
            if (!response.ok) {
                throw new Error(data.error || "Search request failed.");
            }
            let products = Array.isArray(data)
                ? data
                : (data.products || data.results || data.items || []);
            // Keep only products with valid prices
            products = products.filter(product => {
                const price = Number(product.price ?? product.offer_price ?? 0);
                return price > 0;
            });
            if (products.length === 0) {
                if (resultMessage) {
                    resultMessage.textContent =
                        data.error || "No products with valid prices were found.";
                }
                return;
            }
            // Sort from lowest price to highest price
            products.sort((a, b) => {
                const priceA = Number(a.price ?? a.offer_price ?? 0);
                const priceB = Number(b.price ?? b.offer_price ?? 0);
                return priceA - priceB;
            });
            // The first product is the cheapest
            const cheapest = products[0];
            // Display all product cards
            products.forEach((product, index) => {
                const name = product.name || product.title || "Product";
                const store = product.store || product.platform || "Shopping Website";
                const image = product.image || product.image_url || product.gallery?.[0] || "";
                const price = Number(product.price ?? product.offer_price ?? 0);
                const mrp = Number(product.mrp || 0);
                const url = safeURL(product.url || product.deeplink || "");
                const card = document.createElement("article");
                card.className = "result-card product-card";
                if (index === 0) {
                    card.classList.add("cheapest-product");
                }
                card.innerHTML = `
                    ${index === 0 ? `
                        <div class="cheapest-badge">🏆 LOWEST PRICE</div>
                    ` : ""}
                    <div class="product-image-wrap">
                        ${
                            image && safeImageURL(image)
                                ? `<img class="product-image"
                                        src="${escapeHTML(image)}"
                                        alt="${escapeHTML(name)}"
                                        onerror="this.style.display='none'">`
                                : `<div class="product-image-placeholder">
                                       No image available
                                   </div>`
                        }
                    </div>
                    <div class="product-content">
                        <p class="product-store">${escapeHTML(store)}</p>
                        <h3 class="product-name">${escapeHTML(name)}</h3>
                        <div class="product-price">
                            <strong>₹${price.toLocaleString("en-IN")}</strong>
                            ${
                                mrp > price
                                    ? `<del>₹${mrp.toLocaleString("en-IN")}</del>`
                                    : ""
                            }
                        </div>
                        ${
                            index === 0
                                ? `<p class="cheapest-message">
                                       This is the lowest-priced displayed product!
                                   </p>`
                                : ""
                        }
                        ${
                            url
                                ? `<a class="buy-button"
                                      href="${escapeHTML(url)}"
                                      target="_blank"
                                      rel="noopener noreferrer">
                                      View Product
                                   </a>`
                                : ""
                        }
                    </div>
                `;
                resultsGrid.appendChild(card);
            });
            // Separate lowest-price section BELOW all product cards
            const cheapestName = cheapest.name || cheapest.title || "Product";
            const cheapestStore = cheapest.store ||
                                  cheapest.platform ||
                                  "Shopping Website";
            const cheapestPrice = Number(
                cheapest.price ?? cheapest.offer_price ?? 0
            );
            const summary = document.createElement("section");
            summary.className = "lowest-price-summary";
            summary.innerHTML = `
                <div class="summary-icon">🏆</div>
                <p class="summary-label">BEST PRICE FOUND</p>
                <h2>Lowest Price Product</h2>
                <h3 class="summary-product-name">
                    ${escapeHTML(cheapestName)}
                </h3>
                <p class="summary-price">
                    ₹${cheapestPrice.toLocaleString("en-IN")}
                </p>
                <p class="summary-store">
                    Available at:
                    <strong>${escapeHTML(cheapestStore)}</strong>
                </p>
                <p class="summary-note">
                    This is the cheapest item among the displayed results.
                </p>
                ${
                    safeURL(cheapest.url || cheapest.deeplink || "")
                        ? `<a class="buy-now-button"
                              href="${escapeHTML(safeURL(cheapest.url || cheapest.deeplink || ""))}"
                              target="_blank"
                              rel="noopener noreferrer">
                              🛒 Buy Now
                            </a>`
                        : `<p>Purchase link is currently unavailable.</p>`
                }
            `;
            // Append after all product cards
            resultsGrid.appendChild(summary);
            if (resultMessage) {
                resultMessage.textContent =
                    `${products.length} product(s) found, sorted by price.`;
            }
        } catch (error) {
            console.error("PriceWise search error:", error);
            if (resultMessage) {
                resultMessage.textContent =
                    "Unable to load products. Check the Flask terminal for errors.";
            }
        } finally {
            if (searchButton) {
                searchButton.disabled = false;
                searchButton.textContent = "Search";
            }
        }
    });
});
function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}
function safeURL(value) {
    try {
        const url = new URL(value, window.location.origin);
        return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
        return "";
    }
}
function safeImageURL(value) {
    return typeof value === "string" &&
           /^https?:\/\//i.test(value);
}