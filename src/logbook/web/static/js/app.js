// 모든 화면 공통: htmx 요청 전후의 알림 영역(#flash) 처리, 교체 뒤 포커스(data-focus), 편집 행 키보드, 등록·수정 화면의 Esc 취소(data-cancel). 인라인 코드를 쓰지 않으므로 이벤트 위임으로 붙인다.
(function () {
  "use strict";

  var CONNECTION_ERROR = "서버에 연결할 수 없습니다. lb serve가 실행 중인지 확인하세요.";

  function flashArea() {
    return document.getElementById("flash");
  }

  // 새 요청을 보낼 때 지난 오류를 지운다.
  // 빠른 기록 폼의 두 버튼(기록, 타이머 시작)은 결과 줄이 서로 다른 곳(#quick-result, #timer-result)에 뜬다.
  // 한쪽 응답은 다른 쪽을 다시 그리지 않으므로, 폼에서 요청을 보낼 때 지난 결과 줄을 둘 다 지운다.
  document.addEventListener("htmx:beforeRequest", function (event) {
    var area = flashArea();
    if (area) {
      area.replaceChildren();
    }
    var source = event.target;
    if (source && source.closest && source.closest("#quick-form")) {
      ["quick-result", "timer-result"].forEach(function (id) {
        var line = document.getElementById(id);
        if (line) {
          line.remove();
        }
      });
    }
  });

  function isSuccess(status) {
    return status >= 200 && status <= 299;
  }

  function focusInside(root, selector) {
    var field = root.querySelector(selector);
    if (field) {
      field.focus();
    }
  }

  // 교체가 끝난 뒤 포커스를 정한다. 포커스를 받을 요소에는 data-focus를 붙여 둔다(영역마다 하나).
  // 1. 응답이 2xx이고 대상이 편집 중(is-editing)이면 대상 안의 [data-focus]로 옮긴다.
  // 2. 응답이 2xx이고 요청이 POST·PATCH·DELETE면 대상 안의 [data-focus]로 옮긴다.
  // 3. 응답이 4xx이고 대상이 편집 중이면 대상 안의 [data-focus]로 옮긴다.
  // 4. 응답이 4xx이고 대상이 data-refocus 폼(등록·수정 화면)이면 대상 안의 [data-focus](제목 칸)로 옮긴다.
  // 5. 그 밖(GET 필터·주 이동, 타이머 경과 갱신, 그 밖의 오류)은 옮기지 않는다.
  //    1분마다 오는 경과 갱신이 입력 중인 칸의 포커스를 뺏지 않게 한다.
  // afterSwap이 아니라 afterSettle에서 본다. htmx는 id가 같은 요소를 교체하면 settle 전까지
  // 이전 요소의 속성(class 등)을 새 요소에 입혀 둔다. 그래서 표시 행(log-N)이 편집 행으로 바뀐
  // 직후에는 아직 is-editing class가 없다.
  var CHANGING_VERBS = ["post", "patch", "delete"];

  document.addEventListener("htmx:afterSettle", function (event) {
    var target = event.target;
    var detail = event.detail || {};
    var xhr = detail.xhr;
    if (!target || !xhr) {
      return;
    }
    var isEditing = Boolean(target.classList && target.classList.contains("is-editing"));
    var verb = detail.requestConfig && detail.requestConfig.verb;
    var changes = CHANGING_VERBS.indexOf(verb) !== -1;
    var refocus = Boolean(target.hasAttribute && target.hasAttribute("data-refocus"));
    if (isSuccess(xhr.status) ? isEditing || changes : isEditing || refocus) {
      focusInside(target, "[data-focus]");
    }
  });

  // 타이머 경과를 갱신(#timer-elapsed 교체)하면 취소 버튼의 확인 문구도 최신 경과로 바꾼다.
  // 버튼을 다시 그리면 포커스가 사라지므로 hx-confirm 속성만 바꾼다. htmx는 요청을 보낼 때 속성을 읽는다.
  document.addEventListener("htmx:afterSettle", function (event) {
    var target = event.target;
    if (!target || target.id !== "timer-elapsed" || !target.getAttribute) {
      return;
    }
    var message = target.getAttribute("data-cancel-confirm");
    var button = document.querySelector('#timer [hx-post="/timer/cancel"]');
    if (message && button) {
      button.setAttribute("hx-confirm", message);
    }
  });

  // 등록·수정 화면: Esc는 취소 링크([data-cancel])를 누른다. 설명 칸 안에서도 동작한다.
  // 한글 조합 중의 Esc(조합 취소)는 조합 입력기의 몫이라 건드리지 않는다.
  // 선택 상자의 Esc는 목록을 닫는 데 쓰므로 화면 취소로 넘기지 않는다(입력이 사라지지 않게).
  document.addEventListener("keydown", function (event) {
    if (event.isComposing || event.keyCode === 229 || event.key !== "Escape") {
      return;
    }
    if (event.target && event.target.tagName === "SELECT") {
      return;
    }
    var cancel = document.querySelector("a[data-cancel]");
    if (cancel) {
      event.preventDefault();
      cancel.click();
    }
  });

  // 편집 행(.is-editing): Enter는 저장, Esc는 취소. 표 행 안에는 form이 없어서 Enter가 제출되지 않으므로 직접 붙인다.
  // 한글 조합 중의 Enter(조합 확정)·Esc(조합 취소)는 조합 입력기의 몫이라 건드리지 않는다.
  document.addEventListener("keydown", function (event) {
    if (event.isComposing || event.keyCode === 229) {
      return;
    }
    var target = event.target;
    if (!target || !target.closest || (event.key !== "Enter" && event.key !== "Escape")) {
      return;
    }
    var area = target.closest(".is-editing");
    if (!area || target.tagName === "BUTTON" || target.tagName === "TEXTAREA") {
      return;
    }
    var button = area.querySelector(event.key === "Enter" ? "[hx-patch]" : "[hx-get]");
    if (button) {
      event.preventDefault();
      button.click();
    }
  });

  // 색 고르기를 바꾸면 같은 칸의 '자동' 체크를 끈다. 이벤트 위임이라 HTMX로 다시 그린 표에도 동작한다.
  document.addEventListener("input", function (event) {
    var target = event.target;
    if (!target || !target.matches || !target.matches('input[type="color"]')) {
      return;
    }
    var field = target.closest("[data-color-field]");
    var auto = field && field.querySelector('input[type="checkbox"]');
    if (auto) {
      auto.checked = false;
    }
  });

  // 컨텍스트 메뉴(.menu): ⋮ 버튼(.menu__button)이 메뉴(.menu__list, role="menu")를 연다. 이벤트 위임이라 HTMX로 다시 그린 행에도 동작한다.
  // 열기: 클릭, Enter, Space(첫 항목에 포커스), 위·아래 화살표. 이동: 위·아래 화살표(가장자리에서 돌아감), Home·End.
  // 닫기: Esc(⋮로 포커스 복귀), 바깥 클릭, Tab(포커스는 브라우저 순서대로), 항목 선택. 한 번에 하나만 열린다.
  var MENU_ITEMS = '[role="menuitem"]:not([disabled])';

  function menuButton(menu) {
    return menu.querySelector(".menu__button");
  }

  function menuList(menu) {
    return menu.querySelector(".menu__list");
  }

  function closeMenus(except) {
    document.querySelectorAll(".menu").forEach(function (menu) {
      var list = menuList(menu);
      if (menu === except || !list || list.hidden) {
        return;
      }
      list.hidden = true;
      menuButton(menu).setAttribute("aria-expanded", "false");
    });
  }

  function openMenu(menu, focusIndex) {
    closeMenus(menu);
    menuList(menu).hidden = false;
    menuButton(menu).setAttribute("aria-expanded", "true");
    placeMenu(menu);
    var items = menuList(menu).querySelectorAll(MENU_ITEMS);
    if (items.length) {
      items[focusIndex < 0 ? items.length - 1 : focusIndex].focus({ preventScroll: true });
    }
  }

  // 메뉴는 position: fixed라 표 스크롤 상자·구역에 잘리지 않는다. ⋮ 버튼 아래 오른쪽 정렬로 두되,
  // 화면 가장자리 안으로 맞추고 아래 공간이 모자라면 버튼 위로 연다.
  var MENU_GAP = 4;

  function placeMenu(menu) {
    var list = menuList(menu);
    // 이전에 연 자리가 폭 계산(shrink-to-fit)에 끼어들지 않게 먼저 왼쪽 위로 옮기고 잰다.
    list.style.left = "0px";
    list.style.top = "0px";
    var rect = menuButton(menu).getBoundingClientRect();
    var root = document.documentElement;
    var left = Math.min(rect.right - list.offsetWidth, root.clientWidth - list.offsetWidth - MENU_GAP);
    var top = rect.bottom + MENU_GAP;
    if (top + list.offsetHeight > root.clientHeight - MENU_GAP && rect.top - MENU_GAP - list.offsetHeight >= MENU_GAP) {
      top = rect.top - MENU_GAP - list.offsetHeight;
    }
    list.style.left = Math.max(left, MENU_GAP) + "px";
    list.style.top = top + "px";
  }

  // 스크롤·창 크기 변경으로 ⋮ 버튼이 움직이면 메뉴가 떠 있지 않게 닫는다(스크롤은 상자 안 스크롤도 잡도록 capture).
  document.addEventListener("scroll", function () { closeMenus(null); }, true);
  window.addEventListener("resize", function () { closeMenus(null); });

  function closeMenu(menu, returnFocus) {
    closeMenus(null);
    if (returnFocus) {
      menuButton(menu).focus();
    }
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) {
      return;
    }
    var button = target.closest(".menu__button");
    if (button) {
      var menu = button.closest(".menu");
      if (menuList(menu).hidden) {
        openMenu(menu, 0);
      } else {
        closeMenu(menu, false);
      }
      return;
    }
    var item = target.closest('.menu__list [role="menuitem"]');
    if (item) {
      // 항목의 동작(htmx)은 이 클릭에서 그대로 시작된다. 메뉴를 닫고 포커스를 ⋮로 돌린다
      // (삭제 확인 창에서 취소해도 포커스가 사라지지 않는다. 다시 그리면 data-focus 규칙이 옮긴다).
      closeMenu(item.closest(".menu"), true);
      return;
    }
    closeMenus(null);
  });

  document.addEventListener("keydown", function (event) {
    if (event.isComposing || event.keyCode === 229) {
      return;
    }
    var target = event.target;
    var menu = target && target.closest ? target.closest(".menu") : null;
    if (!menu) {
      return;
    }
    var onButton = target.classList.contains("menu__button");
    var key = event.key;
    if (key === "Tab") {
      closeMenus(null);
      return;
    }
    if (onButton) {
      // Enter·Space는 브라우저가 click을 만들므로 여기서는 화살표만 연다.
      if (key === "ArrowDown" || key === "ArrowUp") {
        event.preventDefault();
        openMenu(menu, key === "ArrowDown" ? 0 : -1);
      } else if (key === "Escape" && !menuList(menu).hidden) {
        event.preventDefault();
        closeMenu(menu, true);
      }
      return;
    }
    if (key === "Escape") {
      event.preventDefault();
      closeMenu(menu, true);
      return;
    }
    var items = Array.prototype.slice.call(menuList(menu).querySelectorAll(MENU_ITEMS));
    var index = items.indexOf(target);
    if (index === -1) {
      return;
    }
    var next = null;
    if (key === "ArrowDown") {
      next = items[(index + 1) % items.length];
    } else if (key === "ArrowUp") {
      next = items[(index - 1 + items.length) % items.length];
    } else if (key === "Home") {
      next = items[0];
    } else if (key === "End") {
      next = items[items.length - 1];
    }
    if (next) {
      event.preventDefault();
      next.focus();
    }
  });

  // 서버에 닿지 못한 요청: 서버가 만든 오류 조각이 없으므로 여기서 직접 알린다.
  document.addEventListener("htmx:sendError", function () {
    var area = flashArea();
    if (!area) {
      return;
    }
    var message = document.createElement("p");
    message.className = "flash flash--error";
    message.setAttribute("role", "alert");
    message.textContent = CONNECTION_ERROR;
    area.replaceChildren(message);
  });
})();
