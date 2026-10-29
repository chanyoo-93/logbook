// 보고서 화면 복사. 이벤트 위임이라 htmx가 본문을 바꿔도 동작한다.
// - [data-copy-target]: 대상 요소의 글자를 그대로 복사한다(원문 Markdown).
// - [data-copy-rich]: 표 보기의 절이나 보고서 전체를 서식 있는 HTML과 글(표는 탭 구분) 두 형식으로 함께 넣는다.
//   엑셀·한글은 HTML 표를 셀로 받는다. 자리표시 문구와 버튼([data-copy-skip])은 복사본에서 뺀다.
// - 특이사항·리스크 칸에 저장하지 않은 내용이 있으면 폼에 안내를 보이고,
//   특이사항이 들어가는 복사([data-copy-warn-unsaved])의 결과 줄에 경고를 덧붙인다.
(function () {
  "use strict";

  var COPIED = "보고서를 클립보드에 복사했습니다.";
  var COPY_FAILED = "복사하지 못했습니다. 화면에서 직접 선택해 복사하세요.";
  var UNSAVED_WARNING = " 저장하지 않은 특이사항·리스크는 들어가지 않았습니다.";

  // 서버가 그린 값(defaultValue)과 지금 값이 다르면 저장하지 않은 것이다. 저장하면 폼이 다시 그려져 안내도 사라진다.
  // 충돌(409) 응답은 입력값을 그대로 그리므로 서버가 data-unsaved를 달아 둔다. 이때는 값이 같아도 저장 안 함이다.
  function hasUnsavedNotes() {
    var form = document.getElementById("report-notes");
    if (!form) {
      return false;
    }
    if (form.hasAttribute("data-unsaved")) {
      return true;
    }
    return Array.prototype.some.call(form.querySelectorAll("textarea"), function (field) {
      return field.value !== field.defaultValue;
    });
  }

  document.addEventListener("input", function (event) {
    if (!event.target.closest || !event.target.closest("#report-notes")) {
      return;
    }
    var notice = document.getElementById("report-notes-dirty");
    if (notice) {
      notice.textContent = hasUnsavedNotes() ? notice.getAttribute("data-dirty-text") : "";
    }
  });

  // 같은 문구를 다시 넣어도 화면 낭독기가 읽도록 한 번 비운 뒤 채운다.
  function showStatus(text) {
    var status = document.getElementById("copy-status");
    if (!status) {
      return;
    }
    status.textContent = "";
    window.setTimeout(function () {
      status.textContent = text;
    }, 50);
  }

  // Clipboard API를 못 쓰면 대상을 선택한 뒤 execCommand("copy")로 대신한다. 선택 복사는 서식도 함께 넣는다.
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
    selection.removeAllRanges();
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

  // 복사본: 화면 전용 요소와 id를 빼고, 붙여 넣은 곳에서도 괘선과 숫자 정렬이 남도록 표 속성을 단다.
  function cleanCopy(target) {
    var copy = target.cloneNode(true);
    copy.querySelectorAll("[data-copy-skip]").forEach(function (node) {
      node.remove();
    });
    copy.removeAttribute("id");
    copy.querySelectorAll("[id]").forEach(function (node) {
      node.removeAttribute("id");
    });
    copy.querySelectorAll("table").forEach(function (table) {
      table.setAttribute("border", "1");
      table.setAttribute("cellpadding", "4");
      table.setAttribute("cellspacing", "0");
    });
    copy.querySelectorAll(".num").forEach(function (cell) {
      cell.setAttribute("align", "right");
    });
    return copy;
  }

  function oneLine(node) {
    return node.textContent.replace(/\s+/g, " ").trim();
  }

  // 여러 줄 글(특이사항): 템플릿이 줄마다 <br>로 나눠 두었으므로 <br>을 줄바꿈으로 되돌린다.
  function multiLine(node) {
    return Array.prototype.map
      .call(node.childNodes, function (part) {
        return part.nodeName === "BR" ? "\n" : part.textContent;
      })
      .join("")
      .trim();
  }

  // 글 형식: 제목 앞에 빈 줄, 표는 행마다 칸을 탭으로 잇는다. 특이사항 글은 줄바꿈을 지킨다.
  function collectLines(node, lines) {
    Array.prototype.forEach.call(node.children, function (child) {
      var tag = child.tagName;
      if (tag === "TABLE") {
        Array.prototype.forEach.call(child.rows, function (row) {
          lines.push(Array.prototype.map.call(row.cells, oneLine).join("\t"));
        });
      } else if (/^H[1-6]$/.test(tag)) {
        if (lines.length && lines[lines.length - 1] !== "") {
          lines.push("");
        }
        lines.push(oneLine(child));
      } else if (tag === "P") {
        var text = child.classList.contains("sheet__text") ? multiLine(child) : oneLine(child);
        if (text) {
          lines.push(text);
        }
      } else {
        collectLines(child, lines);
      }
    });
    return lines;
  }

  function copyRich(target) {
    var copy = cleanCopy(target);
    var html = copy.outerHTML;
    // 끝의 빈 줄만 걷어 낸다(trim은 마지막 행의 빈 칸 탭까지 지운다).
    var text = collectLines(copy, []).join("\n").replace(/^\n+|\n+$/g, "") + "\n";
    var fallback = function () {
      var holder = document.createElement("div");
      holder.style.position = "fixed";
      holder.style.left = "-10000px";
      holder.style.top = "0";
      holder.appendChild(copy);
      document.body.appendChild(holder);
      var done = copyBySelection(copy);
      holder.remove();
      return done;
    };
    if (navigator.clipboard && navigator.clipboard.write && window.ClipboardItem) {
      var item = new window.ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" }),
      });
      return navigator.clipboard.write([item]).then(
        function () {
          return true;
        },
        fallback
      );
    }
    return Promise.resolve(fallback());
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-copy-target], [data-copy-rich]");
    if (!button) {
      return;
    }
    var rich = button.hasAttribute("data-copy-rich");
    var target = document.getElementById(
      button.getAttribute(rich ? "data-copy-rich" : "data-copy-target")
    );
    if (!target) {
      showStatus(COPY_FAILED);
      return;
    }
    (rich ? copyRich(target) : copyText(target)).then(function (done) {
      if (!done) {
        showStatus(COPY_FAILED);
        return;
      }
      var warn = button.hasAttribute("data-copy-warn-unsaved") && hasUnsavedNotes();
      showStatus((button.getAttribute("data-copy-done") || COPIED) + (warn ? UNSAVED_WARNING : ""));
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
      panel.tabIndex = 0;
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
