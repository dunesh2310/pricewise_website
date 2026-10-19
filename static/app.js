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

            const products = Array.isArray(data)
                ? data
                : (data.products || data.results || []);

            if (!products.length) {
                if (resultMessage) {
                    resultMessage.textContent =
                        data.error || "No products found. Check your API settings.";
                }
                return;
            }

            products.forEach((product) => {
                const card = document.createElement("article");
                card.className = "result-card product-card";

                const name = escapeHTML(product.name || product.title || "Product");
                const store = escapeHTML(product.store || product.platform || "Store");
                const image = product.image || product.image_url || "";
                const price = Number(product.price || product.offer_price || 0);
                const mrp = Number(product.mrp || 0);
                const url = safeURL(product.url || product.deeplink || "");

                card.innerHTML = `
                    <div class="product-image-wrap">
                        ${
                            image && safeImageURL(image)
                                ? `<img class="product-image" src="${escapeHTML(image)}" alt="${name}" onerror="this.style.display='none'">`
                                : `<div class="product-image-placeholder">No image available</div>`
                        }
                    </div>
                    <div class="product-content">
                        <p class="product-store">${store}</p>
                        <h3 class="product-name">${name}</h3>
                        <p class="product-description">
                            ${escapeHTML(product.description || product.brand || "")}
                        </p>
                        <div class="product-price">
                            <strong>₹${price.toLocaleString("en-IN")}</strong>
                            ${
                                mrp > price
                                    ? `<del>₹${mrp.toLocaleString("en-IN")}</del>`
                                    : ""
                            }
                        </div>
                        ${
                            url
                                ? `<a class="buy-button" href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">View Product</a>`
                                : ""
                        }
                    </div>
                `;

                resultsGrid.appendChild(card);
            });

            if (resultMessage) {
                resultMessage.textContent = `${products.length} product(s) found.`;
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
    return String(value).replace(/[&<>"']/g, (char) => ({
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
    return /^https?:\/\//i.test(value);
}