// 모든 화면 공통: htmx 요청 전후의 알림 영역(#flash) 처리, 교체 뒤 포커스, 편집 행 키보드. 인라인 코드를 쓰지 않으므로 이벤트 위임으로 붙인다.
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

  // 교체가 끝난 뒤 포커스를 정한다(상태 코드별).
  // - 2xx: 빠른 기록 폼은 다음 기록을 바로 입력하도록 시간 칸, 편집 행(is-editing)도 시간 칸.
  //   표 수정·삭제가 성공하면 눌렀던 버튼이 사라지므로 표 제목(tabindex=-1)으로 옮긴다.
  // - 4xx: 편집 행 오류는 시간 칸으로 돌려 고치게 한다. 그 밖의 오류는 입력 중이던 자리를 그대로 둔다.
  document.addEventListener("htmx:afterSwap", function (event) {
    var target = event.target;
    var detail = event.detail || {};
    var xhr = detail.xhr;
    if (!target || !xhr) {
      return;
    }
    var isEditRow = target.classList && target.classList.contains("is-editing");
    if (!isSuccess(xhr.status)) {
      if (isEditRow) {
        focusInside(target, "[name=duration]");
      }
      return;
    }
    var verb = detail.requestConfig && detail.requestConfig.verb;
    if (target.id === "quick-form" || isEditRow) {
      focusInside(target, "[name=duration]");
    } else if (target.id === "log-table" && (verb === "patch" || verb === "delete")) {
      focusInside(target, "#log-table-title");
    }
  });

  // 편집 행: Enter는 저장, Esc는 취소. 표 행 안에는 form이 없어서 Enter가 제출되지 않으므로 직접 붙인다.
  // 한글 조합 중의 Enter(조합 확정)·Esc(조합 취소)는 조합 입력기의 몫이라 건드리지 않는다.
  document.addEventListener("keydown", function (event) {
    if (event.isComposing || event.keyCode === 229) {
      return;
    }
    var target = event.target;
    if (!target || !target.closest || (event.key !== "Enter" && event.key !== "Escape")) {
      return;
    }
    var row = target.closest("tr.is-editing");
    if (!row || target.tagName === "BUTTON") {
      return;
    }
    var button = row.querySelector(event.key === "Enter" ? "[hx-patch]" : "[hx-get]");
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
