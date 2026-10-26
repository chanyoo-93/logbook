// 보고서 화면: [data-copy-target] 버튼이 대상 요소의 텍스트를 클립보드로 복사한다. 이벤트 위임이라 htmx가 본문을 바꿔도 동작한다.
(function () {
  "use strict";

  var COPIED = "보고서를 클립보드에 복사했습니다.";
  var COPY_FAILED = "복사하지 못했습니다. 미리보기에서 직접 선택해 복사하세요.";

  function showStatus(text) {
    var status = document.getElementById("copy-status");
    if (status) {
      status.textContent = text;
    }
  }

  // Clipboard API를 못 쓰면 대상을 선택한 뒤 execCommand("copy")로 대신한다.
  function copyBySelection(target) {
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(target);
    selection.removeAllRanges();
    selection.addRange(range);
    var done = false;
    try {
      done = document.execCommand("copy");
    } catch (error) {
      done = false;
    }
    return done;
  }

  function copyText(target) {
    var text = target.textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return copyBySelection(target);
        }
      );
    }
    return Promise.resolve(copyBySelection(target));
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-copy-target]");
    if (!button) {
      return;
    }
    var target = document.getElementById(button.getAttribute("data-copy-target"));
    if (!target) {
      showStatus(COPY_FAILED);
      return;
    }
    copyText(target).then(function (done) {
      showStatus(done ? button.getAttribute("data-copy-done") || COPIED : COPY_FAILED);
    });
  });
})();

// 보고서 보기 탭: 표 보기(기본)와 원문. JS가 있을 때만 탭을 켜고, 마지막에 고른 보기를 브라우저에 기억한다.
// htmx가 보고서 본문을 바꿔 그리면(주 이동, 특이사항 저장) 다시 켠다.
(function () {
  "use strict";

  var STORAGE_KEY = "logbook.report.view";
  var VIEWS = ["sheet", "raw"];

  function remembered() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return VIEWS.indexOf(value) >= 0 ? value : "sheet";
    } catch (error) {
      return "sheet";
    }
  }

  function remember(view) {
    try {
      window.localStorage.setItem(STORAGE_KEY, view);
    } catch (error) {
      // 저장하지 못해도 이번 화면에서는 고른 보기가 그대로다.
    }
  }

  function select(view, focus) {
    VIEWS.forEach(function (name) {
      var tab = document.getElementById("tab-" + name);
      var panel = document.getElementById("panel-" + name);
      if (!tab || !panel) {
        return;
      }
      var chosen = name === view;
      tab.setAttribute("aria-selected", chosen ? "true" : "false");
      tab.tabIndex = chosen ? 0 : -1;
      panel.hidden = !chosen;
      if (chosen && focus) {
        tab.focus();
      }
    });
  }

  function setup() {
    var views = document.querySelector("[data-report-views]");
    var tabs = document.getElementById("report-tabs");
    if (!views || !tabs || views.classList.contains("report__views--tabs")) {
      return;
    }
    views.classList.add("report__views--tabs");
    tabs.hidden = false;
    var raw = views.querySelector(".report__raw");
    if (raw) {
      raw.open = true;
    }
    select(remembered(), false);
  }

  document.addEventListener("click", function (event) {
    var tab = event.target.closest && event.target.closest("#report-tabs [role=tab]");
    if (!tab) {
      return;
    }
    var view = tab.id.replace("tab-", "");
    select(view, false);
    remember(view);
  });

  document.addEventListener("keydown", function (event) {
    var tab = event.target.closest && event.target.closest("#report-tabs [role=tab]");
    if (!tab) {
      return;
    }
    var index = VIEWS.indexOf(tab.id.replace("tab-", ""));
    var next = null;
    if (event.key === "ArrowRight") {
      next = VIEWS[(index + 1) % VIEWS.length];
    } else if (event.key === "ArrowLeft") {
      next = VIEWS[(index + VIEWS.length - 1) % VIEWS.length];
    } else if (event.key === "Home") {
      next = VIEWS[0];
    } else if (event.key === "End") {
      next = VIEWS[VIEWS.length - 1];
    }
    if (next) {
      event.preventDefault();
      select(next, true);
      remember(next);
    }
  });

  document.addEventListener("DOMContentLoaded", setup);
  document.addEventListener("htmx:afterSettle", setup);
  if (document.readyState !== "loading") {
    setup();
  }
})();
