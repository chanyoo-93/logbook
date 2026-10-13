// 대시보드 차트. #summary의 data-chart(JSON, 값은 분)를 읽어 Chart.js로 그린다.
// 색은 데이터가 가진 값을, 글꼴과 글자색은 CSS 변수를 쓴다. 인라인 스타일은 만들지 않는다(CSP).
(function () {
  "use strict";

  var MINUTES_PER_HOUR = 60;
  // 눈금 간격 후보(분). 눈금이 6개 안팎이 되는 가장 작은 값을 고른다.
  var STEP_CHOICES = [30, 60, 120, 240, 480, 960];
  var MAX_TICKS = 6;
  var TARGET_COLOR_VARIABLE = "--ink";

  // core.duration.format_duration과 같은 표기: 0m, 30m, 1h, 1h 30m
  function formatMinutes(minutes) {
    var hours = Math.floor(minutes / MINUTES_PER_HOUR);
    var rest = Math.round(minutes % MINUTES_PER_HOUR);
    if (hours === 0) {
      return rest + "m";
    }
    return rest === 0 ? hours + "h" : hours + "h " + rest + "m";
  }

  function cssVariable(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function tickStep(maxMinutes) {
    for (var i = 0; i < STEP_CHOICES.length; i += 1) {
      if (maxMinutes / STEP_CHOICES[i] <= MAX_TICKS) {
        return STEP_CHOICES[i];
      }
    }
    return STEP_CHOICES[STEP_CHOICES.length - 1];
  }

  function sum(values) {
    return values.reduce(function (total, value) {
      return total + value;
    }, 0);
  }

  // 지금 그려 둔 차트. OOB로 #summary가 통째로 바뀌면 새 canvas가 생겨 Chart.getChart(canvas)로는
  // 옛 인스턴스를 찾을 수 없으므로, 우리가 만든 인스턴스를 직접 들고 있다가 다시 그리기 전에 모두 없앤다.
  var charts = [];

  function destroyCharts() {
    charts.forEach(function (chart) {
      chart.destroy();
    });
    charts = [];
  }

  function addChart(canvas, config) {
    charts.push(new Chart(canvas, config));
  }

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: prefersReducedMotion() ? false : { duration: 300 },
    };
  }

  function legendLabels() {
    return { usePointStyle: true, boxWidth: 8, boxHeight: 8 };
  }

  function dailyConfig(daily) {
    var labels = daily.labels;
    var dayTotals = daily.totals;
    var bars = daily.datasets.map(function (dataset) {
      return {
        type: "bar",
        label: dataset.label,
        data: dataset.data,
        backgroundColor: dataset.color,
        stack: "minutes",
        maxBarThickness: 48,
      };
    });
    var targetLine = {
      type: "line",
      label: "목표 " + formatMinutes(daily.target),
      data: labels.map(function () {
        return daily.target;
      }),
      borderColor: cssVariable(TARGET_COLOR_VARIABLE),
      borderWidth: 1.5,
      borderDash: [5, 4],
      pointRadius: 0,
      pointHoverRadius: 0,
      fill: false,
    };
    var options = baseOptions();
    options.interaction = { mode: "index", intersect: false };
    options.scales = {
      x: { stacked: true, grid: { display: false } },
      y: {
        stacked: true,
        beginAtZero: true,
        grid: { color: cssVariable("--rule") },
        ticks: {
          stepSize: tickStep(Math.max(daily.target, Math.max.apply(null, dayTotals))),
          callback: function (value) {
            return formatMinutes(value);
          },
        },
      },
    };
    options.plugins = {
      legend: { position: "bottom", labels: legendLabels() },
      tooltip: {
        callbacks: {
          label: function (item) {
            return item.dataset.label + ": " + formatMinutes(item.parsed.y);
          },
          footer: function (items) {
            var index = items[0].dataIndex;
            return "합계: " + formatMinutes(dayTotals[index]);
          },
        },
      },
    };
    return { type: "bar", data: { labels: labels, datasets: bars.concat([targetLine]) }, options: options };
  }

  function doughnutConfig(part) {
    var total = sum(part.data);
    var options = baseOptions();
    options.cutout = "62%";
    options.plugins = {
      legend: { position: "right", labels: legendLabels() },
      tooltip: {
        callbacks: {
          label: function (item) {
            var percent = total === 0 ? 0 : Math.round((item.parsed / total) * 100);
            return item.label + ": " + formatMinutes(item.parsed) + " (" + percent + "%)";
          },
        },
      },
    };
    return {
      type: "doughnut",
      data: {
        labels: part.labels,
        datasets: [
          {
            data: part.data,
            backgroundColor: part.colors,
            borderColor: cssVariable("--surface"),
            borderWidth: 2,
          },
        ],
      },
      options: options,
    };
  }

  function readChartData(summary) {
    try {
      return JSON.parse(summary.getAttribute("data-chart") || "");
    } catch (error) {
      console.error("data-chart를 읽을 수 없습니다:", error);
      return null;
    }
  }

  function drawCharts() {
    if (typeof Chart === "undefined") {
      return;
    }
    // 새 요약에 차트가 없어도(기록 없는 주) 이전 차트는 반드시 정리한다.
    destroyCharts();
    var summary = document.getElementById("summary");
    if (!summary) {
      return;
    }
    var data = readChartData(summary);
    var daily = document.getElementById("chart-daily");
    var projects = document.getElementById("chart-projects");
    var categories = document.getElementById("chart-categories");
    if (!data || !daily || !projects || !categories) {
      return;
    }
    Chart.defaults.font.family = cssVariable("--font-sans");
    Chart.defaults.color = cssVariable("--ink-muted");
    addChart(daily, dailyConfig(data.daily));
    addChart(projects, doughnutConfig(data.projects));
    addChart(categories, doughnutConfig(data.categories));
  }

  // 요약이 htmx로 바뀌면(OOB 교체 포함) 새 요소에 이전 차트가 남지 않게 다시 그린다.
  // 첫 로딩의 htmx:load는 body에서 오므로 건너뛴다(아래에서 직접 그린다).
  document.addEventListener("htmx:load", function (event) {
    var target = event.target;
    if (!(target instanceof Element) || target === document.body) {
      return;
    }
    if (target.id === "summary" || target.querySelector("#summary")) {
      drawCharts();
    }
  });

  drawCharts();
})();
