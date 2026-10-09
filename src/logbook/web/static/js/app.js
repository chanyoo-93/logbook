// 모든 화면 공통: htmx 요청 전후의 알림 영역(#flash) 처리, 빠른 기록·편집 행 포커스, 편집 행 키보드. 인라인 코드를 쓰지 않으므로 이벤트 위임으로 붙인다.
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

  // 성공 응답으로 새로 그려진 입력 영역에 포커스를 둔다. 오류 응답(4xx)은 입력 중이던 자리를 그대로 둔다.
  // - 빠른 기록 폼: 다음 기록을 바로 입력하도록 시간 칸
  // - 기록 표의 편집 행(is-editing): 시간 칸
  document.addEventListener("htmx:afterSwap", function (event) {
    var target = event.target;
    var xhr = event.detail && event.detail.xhr;
    if (!target || !xhr) {
      return;
    }
    if (xhr.status < 200 || xhr.status > 299) {
      return;
    }
    var isQuickForm = target.id === "quick-form";
    var isEditRow = target.classList && target.classList.contains("is-editing");
    if (!isQuickForm && !isEditRow) {
      return;
    }
    var duration = target.querySelector("[name=duration]");
    if (duration) {
      duration.focus();
    }
  });

  // 편집 행: Enter는 저장, Esc는 취소. 표 행 안에는 form이 없어서 Enter가 제출되지 않으므로 직접 붙인다.
  document.addEventListener("keydown", function (event) {
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
