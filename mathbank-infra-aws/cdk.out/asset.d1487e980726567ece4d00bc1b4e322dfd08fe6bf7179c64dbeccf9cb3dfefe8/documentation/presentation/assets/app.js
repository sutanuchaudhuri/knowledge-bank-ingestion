// MathBank Platform Presentation — shared behavior.
// Vanilla JS, no build step. See thought-process.html for why.
(function () {
  "use strict";

  // ── Active nav link ──────────────────────────────────────────────────
  function markActiveNav() {
    var here = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".topnav nav a").forEach(function (a) {
      var href = a.getAttribute("href");
      if (href === here) a.classList.add("active");
    });
  }

  // ── Audience toggle (business vs technical framing) ─────────────────
  function initAudienceToggle() {
    var saved = localStorage.getItem("mathbank_audience") || "technical";
    document.body.setAttribute("data-audience", saved);
    document.querySelectorAll(".audience-toggle button").forEach(function (btn) {
      if (btn.dataset.audience === saved) btn.classList.add("active");
      btn.addEventListener("click", function () {
        document.querySelectorAll(".audience-toggle button").forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
        document.body.setAttribute("data-audience", btn.dataset.audience);
        localStorage.setItem("mathbank_audience", btn.dataset.audience);
      });
    });
  }

  // ── Scroll reveal ─────────────────────────────────────────────────────
  function initReveal() {
    var els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || els.length === 0) {
      els.forEach(function (el) { el.classList.add("in-view"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    els.forEach(function (el) { io.observe(el); });
  }

  // ── Tabs ──────────────────────────────────────────────────────────────
  function initTabs() {
    document.querySelectorAll("[data-tabs]").forEach(function (group) {
      var buttons = group.querySelectorAll(".tabs button");
      var panels = group.querySelectorAll(".tab-panel");
      buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
          buttons.forEach(function (b) { b.classList.remove("active"); });
          panels.forEach(function (p) { p.classList.remove("active"); });
          btn.classList.add("active");
          var target = group.querySelector('[data-panel="' + btn.dataset.tab + '"]');
          if (target) target.classList.add("active");
        });
      });
    });
  }

  // ── Flow pipeline step drill-down ────────────────────────────────────
  function initFlowSteps() {
    document.querySelectorAll(".flow .flow-step").forEach(function (step) {
      step.addEventListener("click", function () {
        var id = step.dataset.detail;
        var flowRoot = step.closest("[data-flow-root]");
        if (!id || !flowRoot) return;
        var wasActive = step.classList.contains("active");
        flowRoot.querySelectorAll(".flow-step").forEach(function (s) { s.classList.remove("active"); });
        flowRoot.querySelectorAll(".flow-detail").forEach(function (d) { d.classList.remove("open"); });
        if (!wasActive) {
          step.classList.add("active");
          var detail = flowRoot.querySelector('[data-detail-for="' + id + '"]');
          if (detail) detail.classList.add("open");
        }
      });
    });
  }

  // ── Mermaid init (diagrams embedded as <pre class="mermaid">) ───────
  function initMermaid() {
    if (typeof mermaid === "undefined") return;
    mermaid.initialize({
      startOnLoad: true,
      theme: "dark",
      themeVariables: {
        background: "#121826",
        primaryColor: "#1b2740",
        primaryTextColor: "#e7ecf5",
        primaryBorderColor: "#6d8dfd",
        lineColor: "#6d8dfd",
        secondaryColor: "#171f30",
        tertiaryColor: "#0f1726",
        fontFamily: "-apple-system, Segoe UI, sans-serif",
      },
      flowchart: { curve: "basis" },
      securityLevel: "loose",
    });
  }

  // ── Real Neo4j subgraph viewer (vis-network) ─────────────────────────
  var LABEL_COLORS = {
    Competition: "#f5a623",
    Paper: "#6d8dfd",
    Problem: "#3ddc97",
    Concept: "#ef5a6f",
    Technique: "#b06ef5",
  };

  function initGraphViewer() {
    var canvas = document.getElementById("graph-canvas");
    if (!canvas || typeof vis === "undefined") return;

    fetch("assets/data/graph-sample.json")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var visNodes = data.nodes.map(function (n) {
          var displayLabel =
            n.label === "Problem" ? n.canonical_code :
            n.label === "Paper" ? n.external_code :
            n.name || n.slug || n.label;
          return {
            id: n.id,
            label: displayLabel,
            group: n.label,
            color: { background: LABEL_COLORS[n.label] || "#888", border: "#0a0e17" },
            font: { color: "#e7ecf5", size: 12 },
            shape: n.label === "Problem" ? "dot" : "box",
            size: n.label === "Problem" ? 10 : undefined,
            raw: n,
          };
        });
        var visEdges = data.edges.map(function (e) {
          return {
            from: e.source,
            to: e.target,
            label: e.type,
            arrows: "to",
            color: { color: "#2b3756", highlight: "#6d8dfd" },
            font: { color: "#6b7a9e", size: 9, strokeWidth: 0 },
            smooth: { type: "continuous" },
          };
        });

        var network = new vis.Network(
          canvas,
          { nodes: new vis.DataSet(visNodes), edges: new vis.DataSet(visEdges) },
          {
            layout: { improvedLayout: true },
            physics: { stabilization: true, barnesHut: { gravitationalConstant: -4000, springLength: 110 } },
            interaction: { hover: true, tooltipDelay: 120 },
          }
        );

        var detailsEl = document.getElementById("node-details");
        network.on("click", function (params) {
          if (!detailsEl) return;
          if (params.nodes.length === 0) {
            detailsEl.innerHTML = "<em>Click a node to inspect its real properties (loaded from a live AuraDB export).</em>";
            return;
          }
          var node = visNodes.find(function (n) { return n.id === params.nodes[0]; });
          if (!node) return;
          var rows = Object.keys(node.raw)
            .filter(function (k) { return k !== "id"; })
            .map(function (k) { return "<tr><td>" + k + "</td><td>" + node.raw[k] + "</td></tr>"; })
            .join("");
          detailsEl.innerHTML =
            '<span class="tag">' + node.raw.label + '</span>' +
            "<table class=\"data\"><tbody>" + rows + "</tbody></table>";
        });
      })
      .catch(function (err) {
        canvas.innerHTML =
          '<p style="padding:20px;color:#9aa7c2">Could not load assets/data/graph-sample.json (' + err + "). " +
          "Serve this folder over HTTP (fetch() of local JSON is blocked under file://) — see thought-process.html.</p>";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    markActiveNav();
    initAudienceToggle();
    initReveal();
    initTabs();
    initFlowSteps();
    initMermaid();
    initGraphViewer();
  });
})();
