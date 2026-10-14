// DiviTrack Frontend Application Logic
document.addEventListener("DOMContentLoaded", () => {
    // State
    let state = {
        timeframe: "all",
        search: "",
        sort: "urgency",
        dividends: [],
        stats: {},
        tokenStatus: {},
        lastUpdated: ""
    };

    // DOM Elements
    const tableBody = document.getElementById("table-body");
    const loadingOverlay = document.getElementById("loading-overlay");
    const emptyState = document.getElementById("empty-state");
    const searchInput = document.getElementById("input-search");
    const clearSearchBtn = document.getElementById("btn-clear-search");
    const sortSelect = document.getElementById("select-sort");
    const refreshBtn = document.getElementById("btn-refresh");
    const exportBtn = document.getElementById("btn-export-csv");
    const timeframeBtns = document.querySelectorAll(".tf-btn");
    const kpiCards = document.querySelectorAll(".kpi-card[data-filter]");
    const footerCount = document.getElementById("footer-count");
    const footerUpdated = document.getElementById("footer-updated");

    // KPI elements
    const kpi5d = document.getElementById("kpi-5d");
    const kpi10d = document.getElementById("kpi-10d");
    const kpi20d = document.getElementById("kpi-20d");
    const kpi30d = document.getElementById("kpi-30d");
    const kpi45d = document.getElementById("kpi-45d");
    const kpi60d = document.getElementById("kpi-60d");
    const kpi75d = document.getElementById("kpi-75d");
    const kpi90d = document.getElementById("kpi-90d");
    const kpiTopYield = document.getElementById("kpi-top-yield");
    const kpiTopStock = document.getElementById("kpi-top-stock");

    // Pill counts
    const pillAll = document.getElementById("pill-all");
    const pill5 = document.getElementById("pill-5");
    const pill10 = document.getElementById("pill-10");
    const pill20 = document.getElementById("pill-20");
    const pill30 = document.getElementById("pill-30");
    const pill45 = document.getElementById("pill-45");
    const pill60 = document.getElementById("pill-60");
    const pill75 = document.getElementById("pill-75");
    const pill90 = document.getElementById("pill-90");


    // Modal elements
    const detailModal = document.getElementById("detail-modal");
    const modalCloseBtn = document.getElementById("modal-close-btn");
    const modalSymbol = document.getElementById("modal-symbol");
    const modalCompanyName = document.getElementById("modal-company-name");
    const modalIsin = document.getElementById("modal-isin");
    const modalDivAmount = document.getElementById("modal-div-amount");
    const modalAnnualDiv = document.getElementById("modal-annual-div");
    const modalDivYield = document.getElementById("modal-div-yield");
    const modalExDate = document.getElementById("modal-ex-date");
    const modalRecDate = document.getElementById("modal-rec-date");
    const modalSubject = document.getElementById("modal-subject");
    const modalHistoryTbody = document.getElementById("modal-history-tbody");

    // Initialize
    loadDividends();

    // Event Listeners: Timeframe Tabs
    timeframeBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            timeframeBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.timeframe = btn.dataset.timeframe;
            loadDividends();
        });
    });

    // Event Listeners: KPI Cards Clickable to filter timeframe
    kpiCards.forEach(card => {
        card.addEventListener("click", () => {
            const filter = card.dataset.filter;
            if (filter) {
                state.timeframe = filter;
                timeframeBtns.forEach(b => {
                    b.classList.toggle("active", b.dataset.timeframe === filter);
                });
                loadDividends();
            }
        });
    });

    // Search Input
    searchInput.addEventListener("input", (e) => {
        state.search = e.target.value.trim().toLowerCase();
        clearSearchBtn.style.display = state.search ? "block" : "none";
        renderTable();
    });

    clearSearchBtn.addEventListener("click", () => {
        searchInput.value = "";
        state.search = "";
        clearSearchBtn.style.display = "none";
        renderTable();
    });

    // Sort Select
    sortSelect.addEventListener("change", (e) => {
        state.sort = e.target.value;
        renderTable();
    });

    // Refresh Button
    refreshBtn.addEventListener("click", async () => {
        const icon = refreshBtn.querySelector(".spin-icon");
        icon.classList.add("spinning");
        showToast("Syncing latest corporate actions...");

        try {
            const res = await fetch("/api/refresh", { method: "POST" });
            const data = await res.json();
            if (data.status === "success") {
                showToast("Data refreshed successfully!");
                await loadDividends();
            }
        } catch (err) {
            console.error("Refresh failed:", err);
            showToast("Failed to refresh data. Please check network/API status.");
        } finally {
            icon.classList.remove("spinning");
            refreshBtn.disabled = false;
        }
    });

    // Export CSV
    exportBtn.addEventListener("click", () => {
        window.location.href = `/api/export?timeframe=${state.timeframe}`;
    });

    // Modal Close
    modalCloseBtn.addEventListener("click", () => {
        detailModal.classList.add("hidden");
    });
    detailModal.addEventListener("click", (e) => {
        if (e.target === detailModal) detailModal.classList.add("hidden");
    });

    // Data Fetcher
    async function loadDividends() {
        showLoading(true);
        try {
            const url = `/api/dividends?timeframe=${state.timeframe}`;
            const res = await fetch(url);
            const data = await res.json();

            state.dividends = data.dividends || [];
            state.stats = data.stats || {};
            state.tokenStatus = data.tokenStatus || data.token_status || {};
            state.lastUpdated = data.last_updated || "Just now";

            updateKPIs();
            renderTable();
        } catch (err) {
            console.error("Error loading dividends:", err);
            showToast("Failed to load dividends data.");
        } finally {
            showLoading(false);
        }
    }

    // Update KPI Header & Pills
    function updateKPIs() {
        const stats = state.stats;
        if (kpi5d) kpi5d.textContent = stats.count_5_days ?? 0;
        if (kpi10d) kpi10d.textContent = stats.count_10_days ?? 0;
        if (kpi20d) kpi20d.textContent = stats.count_20_days ?? 0;
        if (kpi30d) kpi30d.textContent = stats.count_30_days ?? 0;
        if (kpi45d) kpi45d.textContent = stats.count_45_days ?? 0;
        if (kpi60d) kpi60d.textContent = stats.count_60_days ?? 0;
        if (kpi75d) kpi75d.textContent = stats.count_75_days ?? 0;
        if (kpi90d) kpi90d.textContent = stats.count_90_days ?? 0;

        if (pillAll) pillAll.textContent = stats.total_upcoming ?? "-";
        if (pill5) pill5.textContent = stats.count_5_days ?? "-";
        if (pill10) pill10.textContent = stats.count_10_days ?? "-";
        if (pill20) pill20.textContent = stats.count_20_days ?? "-";
        if (pill30) pill30.textContent = stats.count_30_days ?? "-";
        if (pill45) pill45.textContent = stats.count_45_days ?? "-";
        if (pill60) pill60.textContent = stats.count_60_days ?? "-";
        if (pill75) pill75.textContent = stats.count_75_days ?? "-";
        if (pill90) pill90.textContent = stats.count_90_days ?? "-";

        if (stats.highest_yield_stock) {
            const top = stats.highest_yield_stock;
            kpiTopYield.textContent = `${top.dividend_yield.toFixed(2)}%`;
            const displayAmt = top.annual_dividend > 0 ? top.annual_dividend : top.dividend_amount;
            kpiTopStock.textContent = `${top.symbol} (₹${formatNumber(displayAmt)}/sh annual)`;
        } else {
            kpiTopYield.textContent = "-";
            kpiTopStock.textContent = "No yield data";
        }

        footerUpdated.textContent = `Last sync: ${state.lastUpdated}`;
    }


    // Filter, Sort and Render Table
    function renderTable() {
        let items = [...state.dividends];

        // 1. Search Filter
        if (state.search) {
            items = items.filter(d => 
                (d.symbol && d.symbol.toLowerCase().includes(state.search)) ||
                (d.company_name && d.company_name.toLowerCase().includes(state.search))
            );
        }

        // 2. Sort
        items.sort((a, b) => {
            if (state.sort === "urgency") {
                const da = a.days_remaining !== null ? a.days_remaining : 9999;
                const db = b.days_remaining !== null ? b.days_remaining : 9999;
                return da - db;
            } else if (state.sort === "yield-desc") {
                return (b.dividend_yield || 0) - (a.dividend_yield || 0);
            } else if (state.sort === "div-desc") {
                return (b.dividend_amount || 0) - (a.dividend_amount || 0);
            } else if (state.sort === "ex-date") {
                return (a.ex_date || "").localeCompare(b.ex_date || "");
            } else if (state.sort === "symbol") {
                return (a.symbol || "").localeCompare(b.symbol || "");
            }
            return 0;
        });

        // 3. Render Rows
        tableBody.innerHTML = "";
        footerCount.textContent = `Showing ${items.length} of ${state.dividends.length} stocks`;

        if (items.length === 0) {
            emptyState.classList.remove("hidden");
            return;
        } else {
            emptyState.classList.add("hidden");
        }

        items.forEach(stock => {
            const tr = document.createElement("tr");

            // Price Change Tag
            let changeHtml = "";
            if (stock.net_change !== 0 && stock.day_change_percent !== 0) {
                const isUp = stock.net_change > 0;
                const sign = isUp ? "+" : "";
                const cls = isUp ? "up" : "down";
                changeHtml = `<span class="change-tag ${cls}">${sign}${stock.day_change_percent.toFixed(2)}%</span>`;
            }

            // Yield Pill
            let yieldHtml = `<span class="yield-pill">-</span>`;
            if (stock.dividend_yield && stock.dividend_yield > 0) {
                const isHigh = stock.dividend_yield >= 2.0;
                yieldHtml = `<span class="yield-pill ${isHigh ? 'high-yield' : ''}">${stock.dividend_yield.toFixed(2)}%</span>`;
            } else if (!stock.dividend_amount || stock.dividend_amount === 0) {
                yieldHtml = `<span class="yield-pill" style="opacity: 0.65; font-size: 0.72rem;">TBA</span>`;
            }

            // Dividend Amount
            let divAmountHtml = `₹${formatNumber(stock.dividend_amount)}`;
            if (!stock.dividend_amount || stock.dividend_amount === 0) {
                divAmountHtml = `<span class="tba-badge" title="Dividend declared with Record Date fixed; per-share amount to be confirmed in Board meeting">TBA</span>`;
            }

            // Countdown Badge
            const countdownHtml = renderCountdownBadge(stock.days_remaining);

            tr.innerHTML = `
                <td>
                    <div class="stock-identity">
                        <span class="symbol-badge symbol-clickable" title="Click to view ${escapeHtml(stock.company_name || stock.symbol)} details">${escapeHtml(stock.symbol)}</span>
                    </div>
                </td>
                <td class="price-cell">
                    ${stock.ltp > 0 ? `₹${formatNumber(stock.ltp)}` : `<span style="color:var(--text-muted)">-</span>`}
                    ${changeHtml}
                </td>
                <td class="div-amount-cell">
                    ${divAmountHtml}
                </td>
                <td class="annual-div-cell">
                    ${stock.annual_dividend > 0 ? `₹${formatNumber(stock.annual_dividend)}` : `<span style="color:var(--text-muted)">-</span>`}
                </td>
                <td>
                    ${yieldHtml}
                </td>
                <td>
                    <strong>${escapeHtml(stock.ex_date_formatted || stock.ex_date || "-")}</strong>
                </td>
                <td>
                    <span style="color:var(--text-secondary)">${escapeHtml(stock.record_date_formatted || stock.record_date || "-")}</span>
                </td>
                <td>
                    ${countdownHtml}
                </td>
                <td>
                    <button class="action-btn" data-isin="${stock.isin}" data-symbol="${stock.symbol}">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                        <span>History</span>
                    </button>
                </td>
            `;

            // Action button listener
            const actionBtn = tr.querySelector(".action-btn");
            actionBtn.addEventListener("click", () => openCompanyModal(stock));

            // Symbol badge click — same modal as History
            const symbolBadge = tr.querySelector(".symbol-clickable");
            symbolBadge.addEventListener("click", () => openCompanyModal(stock));

            tableBody.appendChild(tr);
        });
    }

    // Countdown Badge Formatter
    function renderCountdownBadge(days) {
        if (days === null || days === undefined) {
            return `<span class="countdown-badge countdown-past">-</span>`;
        }
        if (days < 0) {
            return `<span class="countdown-badge countdown-past">${Math.abs(days)}d ago</span>`;
        }
        if (days === 0) {
            return `<span class="countdown-badge countdown-urgent">Today</span>`;
        }
        if (days === 1) {
            return `<span class="countdown-badge countdown-urgent">Tomorrow</span>`;
        }
        if (days <= 5) {
            return `<span class="countdown-badge countdown-urgent">${days}d left</span>`;
        }
        return `<span class="countdown-badge">${days}d left</span>`;
    }

    // Open Company Detail Modal & Load Dividend Track Record
    async function openCompanyModal(stock) {
        modalSymbol.textContent = stock.symbol;
        modalCompanyName.textContent = stock.company_name;
        modalIsin.textContent = `ISIN: ${stock.isin || "-"} | Series: ${stock.series || "EQ"}`;
        modalDivAmount.textContent = stock.dividend_amount > 0 ? `₹${formatNumber(stock.dividend_amount)} per share` : "Amount TBA (Declared at Board Meeting)";
        if (modalAnnualDiv) {
            modalAnnualDiv.textContent = stock.annual_dividend > 0 ? `₹${formatNumber(stock.annual_dividend)} per share` : (stock.dividend_amount > 0 ? `₹${formatNumber(stock.dividend_amount)} per share` : "TBA");
        }
        modalDivYield.textContent = stock.dividend_yield > 0 ? `${stock.dividend_yield.toFixed(2)}%` : "TBA";
        modalExDate.textContent = stock.ex_date_formatted || stock.ex_date || "-";
        modalRecDate.textContent = stock.record_date_formatted || stock.record_date || "-";
        modalSubject.textContent = stock.subject || stock.dividend_type;

        modalHistoryTbody.innerHTML = `<tr><td colspan="4" class="text-center">Loading dividend history...</td></tr>`;
        detailModal.classList.remove("hidden");

        const lookupKey = (stock.isin && stock.isin !== "-") ? stock.isin : (stock.symbol || "");
        if (!lookupKey) {
            modalHistoryTbody.innerHTML = `<tr><td colspan="4" class="text-center">No dividend history available.</td></tr>`;
            return;
        }

        try {
            const res = await fetch(`/api/stock/${encodeURIComponent(lookupKey)}/history`);
            const data = await res.json();
            if (data.isin && (!stock.isin || stock.isin === "-")) {
                stock.isin = data.isin;
                modalIsin.textContent = `ISIN: ${stock.isin} | Series: ${stock.series || "EQ"}`;
            }
            const history = data.history || [];

            if (history.length === 0) {
                modalHistoryTbody.innerHTML = `<tr><td colspan="4" class="text-center">No past dividend events fetched.</td></tr>`;
                return;
            }

            modalHistoryTbody.innerHTML = "";
            history.forEach(item => {
                const tr = document.createElement("tr");
                const name = item.name || "Dividend";
                const ex = item.expiry_date || "-";
                const amt = item.amount ? `₹${formatNumber(item.amount)}` : "-";
                
                // Extract record date from item or event_details
                let recDate = item.record_date || "-";
                if (recDate === "-" && item.event_details && Array.isArray(item.event_details)) {
                    const recObj = item.event_details.find(d => /record/i.test(d.name || ""));
                    if (recObj) recDate = recObj.value || "-";
                }

                tr.innerHTML = `
                    <td><strong>${escapeHtml(name)}</strong></td>
                    <td>${escapeHtml(ex)}</td>
                    <td><strong>${amt}</strong></td>
                    <td>${escapeHtml(recDate)}</td>
                `;
                modalHistoryTbody.appendChild(tr);
            });
        } catch (err) {
            console.error("Failed to fetch dividend history:", err);
            modalHistoryTbody.innerHTML = `<tr><td colspan="4" class="text-center">No past dividend events recorded.</td></tr>`;
        }
    }

    // Helper: Show/Hide Loading
    function showLoading(show) {
        if (show) loadingOverlay.classList.remove("hidden");
        else loadingOverlay.classList.add("hidden");
    }

    // Helper: Toast Notifications
    function showToast(msg) {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = "toast";
        toast.textContent = msg;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    // Helper: Format Number with decimals
    function formatNumber(num) {
        if (num === null || num === undefined || isNaN(num)) return "-";
        return Number(num).toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // Helper: Escape HTML
    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Global Reset Filter
    window.resetFilters = function() {
        state.timeframe = "all";
        state.search = "";
        searchInput.value = "";
        clearSearchBtn.style.display = "none";
        timeframeBtns.forEach(b => b.classList.toggle("active", b.dataset.timeframe === "all"));
        loadDividends();
    };
});
