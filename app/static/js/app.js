/**
 * Carbon Footprint Awareness Platform — Frontend Logic
 *
 * Handles tab navigation, form submission, API calls,
 * chat interaction, and accessibility features.
 *
 * Security: Uses textContent (not innerHTML) for user data,
 * manages CSRF tokens, and debounces input.
 */

"use strict";

// =============================================================================
// CSRF Token Management
// =============================================================================

const CsrfManager = {
    _token: null,

    async initialize() {
        try {
            const response = await fetch("/api/csrf-token", {
                method: "GET",
                credentials: "same-origin",
            });
            if (response.ok) {
                const data = await response.json();
                this._token = data.csrf_token;
            }
        } catch (error) {
            console.warn("CSRF token fetch failed:", error);
        }
    },

    getToken() {
        if (!this._token) {
            // Fallback: read from cookie
            const match = document.cookie.match(/csrf_token=([^;]+)/);
            if (match) {
                this._token = match[1];
            }
        }
        return this._token || "";
    },

    getHeaders() {
        return {
            "Content-Type": "application/json",
            "X-CSRF-Token": this.getToken(),
        };
    },
};

// =============================================================================
// API Client — centralized fetch with error handling
// =============================================================================

const ApiClient = {
    async post(url, body) {
        const response = await fetch(url, {
            method: "POST",
            headers: CsrfManager.getHeaders(),
            credentials: "same-origin",
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const message = errorData.detail || `Request failed (${response.status})`;
            throw new Error(message);
        }

        return response.json();
    },

    async get(url) {
        const response = await fetch(url, {
            method: "GET",
            credentials: "same-origin",
        });

        if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
        }

        return response.json();
    },
};

// =============================================================================
// Toast Notifications
// =============================================================================

const Toast = {
    _element: null,
    _messageElement: null,
    _timeout: null,

    initialize() {
        this._element = document.getElementById("toast");
        this._messageElement = document.getElementById("toast-message");
    },

    show(message, type = "success", duration = 3000) {
        if (this._timeout) {
            clearTimeout(this._timeout);
        }

        this._messageElement.textContent = message;
        this._element.className = `toast toast--visible toast--${type}`;
        this._element.hidden = false;

        this._timeout = setTimeout(() => {
            this._element.classList.remove("toast--visible");
            setTimeout(() => {
                this._element.hidden = true;
            }, 500);
        }, duration);
    },
};

// =============================================================================
// Tab Navigation — keyboard accessible
// =============================================================================

const TabManager = {
    _tabs: [],
    _panels: [],

    initialize() {
        this._tabs = Array.from(document.querySelectorAll("[role='tab']"));
        this._panels = Array.from(document.querySelectorAll("[role='tabpanel']"));

        this._tabs.forEach((tab) => {
            tab.addEventListener("click", () => this._activateTab(tab));
            tab.addEventListener("keydown", (event) => this._handleKeydown(event, tab));
        });
    },

    _activateTab(selectedTab) {
        // Deactivate all tabs
        this._tabs.forEach((tab) => {
            tab.setAttribute("aria-selected", "false");
            tab.classList.remove("nav__tab--active");
            tab.setAttribute("tabindex", "-1");
        });

        // Activate selected tab
        selectedTab.setAttribute("aria-selected", "true");
        selectedTab.classList.add("nav__tab--active");
        selectedTab.setAttribute("tabindex", "0");
        selectedTab.focus();

        // Toggle panels
        const targetPanelId = selectedTab.getAttribute("aria-controls");
        this._panels.forEach((panel) => {
            if (panel.id === targetPanelId) {
                panel.hidden = false;
                panel.classList.add("panel--active");
            } else {
                panel.hidden = true;
                panel.classList.remove("panel--active");
            }
        });

        // Track tab activation
        Analytics.trackEvent("tab_activated", { tab_id: targetPanelId });
    },

    _handleKeydown(event, currentTab) {
        const currentIndex = this._tabs.indexOf(currentTab);
        let targetIndex = -1;

        switch (event.key) {
            case "ArrowRight":
            case "ArrowDown":
                event.preventDefault();
                targetIndex = (currentIndex + 1) % this._tabs.length;
                break;
            case "ArrowLeft":
            case "ArrowUp":
                event.preventDefault();
                targetIndex = (currentIndex - 1 + this._tabs.length) % this._tabs.length;
                break;
            case "Home":
                event.preventDefault();
                targetIndex = 0;
                break;
            case "End":
                event.preventDefault();
                targetIndex = this._tabs.length - 1;
                break;
            default:
                return;
        }

        if (targetIndex >= 0) {
            this._activateTab(this._tabs[targetIndex]);
        }
    },
};

// =============================================================================
// Calculator Form
// =============================================================================

const Calculator = {
    _form: null,
    _resultsArea: null,

    initialize() {
        this._form = document.getElementById("calculator-form");
        this._resultsArea = document.getElementById("results-area");

        this._form.addEventListener("submit", (event) => {
            event.preventDefault();
            this._calculate();
        });

        document.getElementById("btn-track").addEventListener("click", () => {
            this._track();
        });

        // Live slider updates
        const distanceSlider = document.getElementById("transport-distance");
        const distanceDisplay = document.getElementById("distance-display");
        const fuelDisplay = document.getElementById("fuel-burn-display");
        const co2Display = document.getElementById("co2-live-display");
        const modeSelect = document.getElementById("transport-mode");

        const updateLiveStats = () => {
            const distance = parseFloat(distanceSlider.value) || 0;
            const mode = modeSelect.value;
            distanceDisplay.textContent = distance;

            // Simple estimates
            let fuel = 0;
            let co2 = 0;
            if (mode === "car_petrol") { fuel = distance / 12; co2 = distance * 0.192; }
            else if (mode === "car_diesel") { fuel = distance / 15; co2 = distance * 0.171; }
            else if (mode === "car_electric") { co2 = distance * 0.053; }
            else if (mode === "bus") { fuel = distance / 40; co2 = distance * 0.089; }
            else if (mode === "train") { co2 = distance * 0.041; }
            else if (mode === "flight_short") { fuel = distance / 20; co2 = distance * 0.255; }
            else if (mode === "flight_long") { fuel = distance / 25; co2 = distance * 0.195; }

            fuelDisplay.textContent = fuel.toFixed(1);
            co2Display.textContent = co2.toFixed(1);
        };

        distanceSlider.addEventListener("input", updateLiveStats);
        modeSelect.addEventListener("change", updateLiveStats);
    },

    _buildPayload() {
        const payload = { transport: [], energy: [], food: [], waste: [] };

        // Transport
        const transportMode = document.getElementById("transport-mode").value;
        const transportDistance = parseFloat(document.getElementById("transport-distance").value);
        if (transportMode && transportDistance > 0) {
            payload.transport.push({ mode: transportMode, distance_km: transportDistance });
        }

        // Energy
        const energySource = document.getElementById("energy-source").value;
        const energyAmount = parseFloat(document.getElementById("energy-amount").value);
        if (energySource && energyAmount > 0) {
            payload.energy.push({ source: energySource, amount_kwh: energyAmount });
        }

        // Food
        const foodType = document.getElementById("food-type").value;
        const foodServings = parseFloat(document.getElementById("food-servings").value);
        if (foodType && foodServings > 0) {
            payload.food.push({ food_type: foodType, servings: foodServings });
        }

        // Waste
        const wasteType = document.getElementById("waste-type").value;
        const wasteWeight = parseFloat(document.getElementById("waste-weight").value);
        if (wasteType && wasteWeight > 0) {
            payload.waste.push({ waste_type: wasteType, weight_kg: wasteWeight });
        }

        return payload;
    },

    _hasData(payload) {
        return (
            payload.transport.length > 0 ||
            payload.energy.length > 0 ||
            payload.food.length > 0 ||
            payload.waste.length > 0
        );
    },

    async _calculate() {
        const payload = this._buildPayload();

        if (!this._hasData(payload)) {
            Toast.show("Please fill in at least one category.", "error");
            return;
        }

        const button = document.getElementById("btn-calculate");
        button.disabled = true;
        button.innerHTML = '<span class="spinner"></span> Calculating...';

        try {
            const data = await ApiClient.post("/api/carbon/calculate", payload);
            this._displayResults(data);
            Toast.show("Footprint calculated successfully!", "success");
            
            // Track successful carbon calculation
            Analytics.trackEvent("carbon_calculated", {
                total_co2: data.total_co2_kg,
                rating: data.rating
            });
        } catch (error) {
            Toast.show(error.message, "error");
        } finally {
            button.disabled = false;
            button.innerHTML = '<span aria-hidden="true">📊</span> Calculate Footprint';
        }
    },

    _displayResults(data) {
        this._resultsArea.hidden = false;

        // Total CO2
        document.getElementById("result-total").textContent = data.total_co2_kg.toFixed(2);

        // Rating badge
        const badge = document.getElementById("result-rating");
        badge.textContent = data.rating;
        badge.setAttribute("data-rating", data.rating);

        // Comparison text
        document.getElementById("result-comparison").textContent = data.comparison_to_average;

        // Breakdown bars
        const breakdownContainer = document.getElementById("result-breakdown");
        breakdownContainer.innerHTML = ""; // Safe: no user data

        data.breakdown.forEach((item) => {
            const element = document.createElement("div");
            element.className = "breakdown-item";
            element.setAttribute("role", "listitem");

            const category = document.createElement("div");
            category.className = "breakdown-item__category";
            category.textContent = item.category;

            const value = document.createElement("div");
            value.className = "breakdown-item__value";
            value.textContent = `${item.co2_kg.toFixed(2)} kg`;

            const bar = document.createElement("div");
            bar.className = "breakdown-item__bar";
            bar.setAttribute("role", "progressbar");
            bar.setAttribute("aria-valuenow", item.percentage.toString());
            bar.setAttribute("aria-valuemin", "0");
            bar.setAttribute("aria-valuemax", "100");
            bar.setAttribute("aria-label", `${item.category}: ${item.percentage}%`);

            const fill = document.createElement("div");
            fill.className = "breakdown-item__fill";
            // Defer width change to trigger CSS transition
            requestAnimationFrame(() => {
                fill.style.width = `${item.percentage}%`;
            });

            bar.appendChild(fill);
            element.appendChild(category);
            element.appendChild(value);
            element.appendChild(bar);
            breakdownContainer.appendChild(element);
        });

        // Scroll results into view
        this._resultsArea.scrollIntoView({ behavior: "smooth", block: "nearest" });

        // Store latest data for insights
        this._lastPayload = this._buildPayload();
    },

    async _track() {
        const payload = this._buildPayload();

        if (!this._hasData(payload)) {
            Toast.show("Please fill in at least one category to track.", "error");
            return;
        }

        const button = document.getElementById("btn-track");
        button.disabled = true;

        try {
            const data = await ApiClient.post("/api/carbon/track", payload);
            Toast.show("Entry saved to tracker!", "success");
            Tracker.refresh();
            
            // Track successful carbon logging
            Analytics.trackEvent("carbon_tracked", {
                rating: data.summary ? data.summary.rating : "unknown"
            });
        } catch (error) {
            Toast.show(error.message, "error");
        } finally {
            button.disabled = false;
        }
    },

    getLastPayload() {
        return this._lastPayload || null;
    },
};

// =============================================================================
// Tracker
// =============================================================================

const Tracker = {
    _entriesContainer: null,
    _emptyState: null,

    initialize() {
        this._entriesContainer = document.getElementById("tracker-entries");
        this._emptyState = document.getElementById("tracker-empty");
    },

    async refresh() {
        try {
            const data = await ApiClient.get("/api/carbon/history");

            if (data.entries.length === 0) {
                this._emptyState.hidden = false;
                this._entriesContainer.innerHTML = "";
                return;
            }

            this._emptyState.hidden = true;
            this._entriesContainer.innerHTML = ""; // Safe: no user data used in innerHTML

            data.entries.forEach((record, index) => {
                const entry = document.createElement("div");
                entry.className = "tracker-entry";
                entry.setAttribute("role", "listitem");

                const number = document.createElement("span");
                number.className = "tracker-entry__number";
                number.textContent = (index + 1).toString();

                const details = document.createElement("div");
                details.className = "tracker-entry__details";

                const co2 = document.createElement("span");
                co2.className = "tracker-entry__co2";
                co2.textContent = `${record.summary.total_co2_kg.toFixed(2)} kg CO₂`;

                const rating = document.createElement("span");
                rating.className = "tracker-entry__rating";
                rating.textContent = `Rating: ${record.summary.rating}`;

                details.appendChild(co2);
                entry.appendChild(number);
                entry.appendChild(details);
                entry.appendChild(rating);
                this._entriesContainer.appendChild(entry);
            });
        } catch (error) {
            Toast.show("Failed to load tracking history.", "error");
        }
    },
};

// =============================================================================
// Insights
// =============================================================================

const Insights = {
    _cardsContainer: null,
    _emptyState: null,

    initialize() {
        this._cardsContainer = document.getElementById("insights-cards");
        this._emptyState = document.getElementById("insights-empty");

        // Auto-fetch insights when tab is activated
        document.getElementById("tab-insights").addEventListener("click", () => {
            this._fetchInsights();
        });
    },

    async _fetchInsights() {
        const payload = Calculator.getLastPayload();

        if (!payload) {
            this._emptyState.hidden = false;
            this._cardsContainer.innerHTML = "";
            return;
        }

        try {
            const data = await ApiClient.post("/api/insights", payload);
            this._displayInsights(data);
        } catch (error) {
            Toast.show("Failed to generate insights.", "error");
        }
    },

    _displayInsights(data) {
        this._emptyState.hidden = true;
        this._cardsContainer.innerHTML = ""; // Safe: no user data

        // Summary header
        const summary = document.createElement("div");
        summary.className = "insights__summary glass-card";

        const summaryText = document.createElement("p");
        summaryText.className = "insights__summary-text";
        summaryText.textContent = `Your highest impact area is `;

        const highlight = document.createElement("strong");
        highlight.className = "insights__summary-highlight";
        highlight.textContent = data.highest_impact_category;
        summaryText.appendChild(highlight);

        const reduction = document.createTextNode(
            `. Potential reduction: ${data.potential_reduction_kg.toFixed(1)} kg CO₂.`
        );
        summaryText.appendChild(reduction);
        summary.appendChild(summaryText);
        this._cardsContainer.appendChild(summary);

        // Insight cards
        data.insights.forEach((insight) => {
            const card = document.createElement("article");
            card.className = "insight-card";

            const title = document.createElement("h3");
            title.className = "insight-card__title";
            title.textContent = insight.title;

            const description = document.createElement("p");
            description.className = "insight-card__description";
            description.textContent = insight.description;

            const meta = document.createElement("div");
            meta.className = "insight-card__meta";

            const impactTag = document.createElement("span");
            impactTag.className = "insight-card__tag";
            impactTag.textContent = `Impact: ${insight.impact}`;

            const difficultyTag = document.createElement("span");
            difficultyTag.className = "insight-card__tag insight-card__tag--difficulty";
            difficultyTag.textContent = `Difficulty: ${insight.difficulty}`;

            meta.appendChild(impactTag);
            meta.appendChild(difficultyTag);

            card.appendChild(title);
            card.appendChild(description);
            card.appendChild(meta);
            this._cardsContainer.appendChild(card);
        });
    },
};

// =============================================================================
// Chat
// =============================================================================

const Chat = {
    _messagesContainer: null,
    _form: null,
    _input: null,
    _sendButton: null,
    _statusElement: null,
    _isProcessing: false,

    initialize() {
        this._messagesContainer = document.getElementById("chat-messages");
        this._form = document.getElementById("chat-form");
        this._input = document.getElementById("chat-input");
        this._sendButton = document.getElementById("btn-send");
        this._statusElement = document.getElementById("chat-status");

        this._form.addEventListener("submit", (event) => {
            event.preventDefault();
            this._sendMessage();
        });
    },

    async _sendMessage() {
        const message = this._input.value.trim();

        if (!message || this._isProcessing) {
            return;
        }

        this._isProcessing = true;
        this._input.value = "";
        this._sendButton.disabled = true;

        // Add user bubble
        this._addBubble(message, "user");

        // Show typing indicator
        const typingIndicator = this._addTypingIndicator();

        // Update status
        this._statusElement.textContent = "AI is thinking...";

        try {
            const data = await ApiClient.post("/api/chat", { message });

            // Remove typing indicator
            typingIndicator.remove();

            // Add AI response bubble
            this._addBubble(data.reply, "ai", data.provider, data.fallback_used);

            if (data.fallback_used) {
                this._statusElement.textContent = `Responded via ${data.provider} (fallback)`;
            } else {
                this._statusElement.textContent = `Responded via ${data.provider}`;
            }

            // Track successful chat response
            Analytics.trackEvent("chat_message_sent", {
                provider: data.provider,
                fallback_used: data.fallback_used
            });
        } catch (error) {
            typingIndicator.remove();
            this._addBubble(
                "Sorry, I couldn't process your request. Please try again.",
                "ai"
            );
            this._statusElement.textContent = "Error — please try again";
            Toast.show(error.message, "error");
        } finally {
            this._isProcessing = false;
            this._sendButton.disabled = false;
            this._input.focus();
        }
    },

    _addBubble(text, type, provider = null, fallbackUsed = false) {
        const bubble = document.createElement("div");
        bubble.className = `chat__bubble chat__bubble--${type}`;
        bubble.textContent = text; // Safe: textContent prevents XSS

        if (provider && type === "ai") {
            const providerLabel = document.createElement("div");
            providerLabel.className = "chat__bubble-provider";
            providerLabel.textContent = fallbackUsed
                ? `via ${provider} (fallback)`
                : `via ${provider}`;
            bubble.appendChild(providerLabel);
        }

        this._messagesContainer.appendChild(bubble);
        this._scrollToBottom();
    },

    _addTypingIndicator() {
        const indicator = document.createElement("div");
        indicator.className = "typing-indicator";
        indicator.setAttribute("aria-label", "AI is typing");

        for (let i = 0; i < 3; i++) {
            const dot = document.createElement("span");
            indicator.appendChild(dot);
        }

        this._messagesContainer.appendChild(indicator);
        this._scrollToBottom();
        return indicator;
    },

    _scrollToBottom() {
        this._messagesContainer.scrollTop = this._messagesContainer.scrollHeight;
    },
};

// =============================================================================
// Google Analytics Manager
// =============================================================================

const Analytics = {
    _measurementId: null,
    _simulator: true,

    async initialize() {
        try {
            const config = await ApiClient.get("/api/analytics/config");
            this._measurementId = config.ga_measurement_id;
            this._simulator = config.simulator_enabled;

            if (!this._simulator && this._measurementId && this._measurementId !== "G-MOCKMEASUREID") {
                this._loadScript();
            } else {
                console.log(`[ANALYTICS SIMULATOR] Loaded GA4 configuration. Measurement ID: ${this._measurementId}`);
            }
        } catch (error) {
            console.warn("Analytics initialization failed:", error);
        }
    },

    _loadScript() {
        const script = document.createElement("script");
        script.src = `https://www.googletagmanager.com/gtag/js?id=${this._measurementId}`;
        script.async = true;
        document.head.appendChild(script);

        window.dataLayer = window.dataLayer || [];
        window.gtag = function () {
            window.dataLayer.push(arguments);
        };
        window.gtag("js", new Date());
        window.gtag("config", this._measurementId, {
            cookie_flags: "SameSite=None;Secure",
        });
    },

    trackEvent(eventName, params = {}) {
        if (!this._simulator && window.gtag) {
            window.gtag("event", eventName, params);
        } else {
            console.log(`[ANALYTICS SIMULATOR] Event tracked: '${eventName}'`, params);
        }
    },
};

// =============================================================================
// Application Initialization
// =============================================================================

document.addEventListener("DOMContentLoaded", async () => {
    // Initialize CSRF first
    await CsrfManager.initialize();

    // Initialize GA4 analytics
    await Analytics.initialize();

    // Initialize all modules
    Toast.initialize();
    TabManager.initialize();
    Calculator.initialize();
    Tracker.initialize();
    Insights.initialize();
    Chat.initialize();
});
