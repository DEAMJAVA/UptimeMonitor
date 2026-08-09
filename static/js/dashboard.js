(function () {
  let currentRange = "24h";
  let chart = null;
  let pollTimer = null;

  const RANGE_AGO_LABELS = {
    "24h": "24h ago",
    "7d": "7d ago",
    "1m": "1m ago",
    "3m": "3m ago",
    "6m": "6m ago",
    "1y": "1y ago",
  };

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    seconds = Math.max(0, Math.round(seconds));
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  function formatDateTime(ts) {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  }

  function statusBadgeHtml(status, isPaused) {
    if (isPaused) return '<span class="badge badge-paused">Paused</span>';
    if (status === "up") return '<span class="badge badge-up">Up</span>';
    if (status === "down") return '<span class="badge badge-down">Down</span>';
    if (status === "unmonitored") return '<span class="badge badge-unmonitored">Unmonitored</span>';
    return '<span class="badge badge-unknown">Unknown</span>';
  }

  function renderStats(data) {
    document.getElementById("stat-status").innerHTML = statusBadgeHtml(data.current_status, data.is_paused);
    document.getElementById("stat-uptime").textContent =
      data.uptime_pct === null ? "—" : data.uptime_pct.toFixed(2) + "%";
    document.getElementById("stat-downtime").textContent = formatDuration(data.total_downtime_seconds);
    document.getElementById("stat-longest").textContent = formatDuration(data.longest_downtime_seconds);
    document.getElementById("stat-incidents").textContent = data.total_incidents;
    document.getElementById("live-status-badge").innerHTML = statusBadgeHtml(data.current_status, data.is_paused);

    const coverageEl = document.getElementById("coverage-note");
    const notes = [];
    if (data.monitored_seconds < data.window_seconds * 0.98) {
      notes.push(
        data.monitored_seconds <= 0
          ? "This monitor has no data yet for the selected range."
          : `Based on ${formatDuration(data.monitored_seconds)} of monitoring data — this monitor hasn't existed for the full selected range.`
      );
    }
    if (data.unmonitored_seconds > 0) {
      notes.push(
        `${formatDuration(data.unmonitored_seconds)} of this period is excluded from uptime % — our server lost connectivity, so we couldn't tell if the target was actually reachable.`
      );
    }
    if (notes.length) {
      coverageEl.textContent = notes.join(" ");
      coverageEl.style.display = "block";
    } else {
      coverageEl.style.display = "none";
    }
  }

  function renderChart(series) {
    const ctx = document.getElementById("responseChart").getContext("2d");
    const labels = series.map((p) => formatDateTime(p.timestamp));
    const values = series.map((p) => p.avg_response_ms);

    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.update();
      return;
    }

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Avg response time (ms)",
            data: values,
            borderColor: "#e63946",
            backgroundColor: "rgba(230, 57, 70, 0.15)",
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            ticks: { color: "#9a9aa2", maxTicksLimit: 8 },
            grid: { color: "#2a2a2e" },
          },
          y: {
            ticks: { color: "#9a9aa2" },
            grid: { color: "#2a2a2e" },
            beginAtZero: true,
          },
        },
        plugins: {
          legend: { labels: { color: "#eaeaea" } },
        },
      },
    });
  }

  function renderIncidents(incidents) {
    const container = document.getElementById("incidents-container");
    if (!incidents.length) {
      container.innerHTML = '<div class="no-data">No incidents in this time range.</div>';
      return;
    }

    let rows = incidents
      .map((inc) => {
        const statusLabel =
          inc.status === "ongoing"
            ? '<span class="badge badge-down">Ongoing</span>'
            : '<span class="badge badge-up">Resolved</span>';
        return `<tr>
          <td>${formatDateTime(inc.started_at)}</td>
          <td>${inc.ended_at ? formatDateTime(inc.ended_at) : "—"}</td>
          <td>${inc.duration_seconds !== null ? formatDuration(inc.duration_seconds) : "ongoing"}</td>
          <td>${statusLabel}</td>
        </tr>`;
      })
      .join("");

    container.innerHTML = `
      <div class="table-scroll">
        <table class="incidents-table">
          <thead>
            <tr><th>Started</th><th>Resolved</th><th>Duration</th><th>Status</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  function renderHistory(bars, range) {
    const container = document.getElementById("history-bars");
    container.innerHTML = bars
      .map((b) => {
        let pct;
        if (b.state === "nodata") {
          pct = "no data";
        } else if (b.state === "unmonitored") {
          pct = "unmonitored (our network was down)";
        } else {
          pct = `${Math.round((1 - b.down_fraction) * 100)}% up`;
        }
        const title = `${formatDateTime(b.start)} — ${formatDateTime(b.end)}\n${pct}`;
        return `<div class="history-bar state-${b.state}" title="${title}"></div>`;
      })
      .join("");

    document.getElementById("history-label-start").textContent =
      RANGE_AGO_LABELS[range] || "Start";
  }

  function loadData(range) {
    fetch(`${window.DATA_URL_BASE}?range=${encodeURIComponent(range)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) return;
        renderStats(data);
        renderChart(data.response_series);
        renderIncidents(data.incidents);
        renderHistory(data.history || [], range);
      })
      .catch((err) => console.error("Failed to load monitor data", err));
  }

  function setActiveButton(range) {
    document.querySelectorAll(".range-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.range === range);
    });
  }

  document.getElementById("range-selector").addEventListener("click", (e) => {
    const btn = e.target.closest(".range-btn");
    if (!btn) return;
    currentRange = btn.dataset.range;
    setActiveButton(currentRange);
    loadData(currentRange);
  });

  // Initial load + light polling so status/graph stay fresh without a manual refresh.
  loadData(currentRange);
  pollTimer = setInterval(() => loadData(currentRange), 20000);
  window.addEventListener("beforeunload", () => clearInterval(pollTimer));
})();
