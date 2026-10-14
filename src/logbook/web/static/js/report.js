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
      showStatus(done ? COPIED : COPY_FAILED);
    });
  });
})();
