// 모든 화면 공통: htmx 요청 전후의 알림 영역(#flash) 처리, 교체 뒤 포커스(data-focus), 편집 행·카드 키보드. 인라인 코드를 쓰지 않으므로 이벤트 위임으로 붙인다.
(function () {
  "use strict";

  var CONNECTION_ERROR = "서버에 연결할 수 없습니다. lb serve가 실행 중인지 확인하세요.";

  function flashArea() {
    return document.getElementById("flash");
  }

  // 새 요청을 보낼 때 지난 오류를 지운다.
  document.addEventListener("htmx:beforeRequest", function () {
    var area = flashArea();
    if (area) {
      area.replaceChildren();
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
  // 4. 그 밖(GET 필터·주 이동, 타이머 경과 갱신, 그 밖의 오류)은 옮기지 않는다.
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
    if (isSuccess(xhr.status) ? isEditing || changes : isEditing) {
      focusInside(target, "[data-focus]");
    }
  });

  // 편집 행·편집 카드(.is-editing): Enter는 저장, Esc는 취소. 표 행 안에는 form이 없어서 Enter가 제출되지 않으므로 직접 붙인다.
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
