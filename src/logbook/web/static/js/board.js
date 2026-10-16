// 태스크 보드: 카드를 열 사이로 끌어 놓아 상태를 바꾼다(SortableJS). 인라인 코드를 쓰지 않으므로 이벤트는 여기서 붙인다.
// 상태 변경은 버튼 때와 같은 주소(POST /tasks/{id}/status)를 쓰고, 성공하면 서버가 보드를 통째로 다시 그린다.
// 실패하면 오류 문구는 #flash가 보여 주고, 끈 카드는 이 파일이 원래 열의 원래 자리로 되돌린다.
// 보드를 다시 불러오지 않는다: 요청을 보내는 순간 app.js가 #flash를 비워 오류 문구가 사라지고,
// 서버가 꺼졌을 때는 다시 불러오기도 실패하기 때문이다.
(function () {
  "use strict";

  var LIST_SELECTOR = ".board__cards";
  var CARD_SELECTOR = ".task-card";

  function boardLists() {
    return Array.prototype.slice.call(document.querySelectorAll(LIST_SELECTOR));
  }

  // 요청이 끝날 때까지 끌기를 잠가 요청이 겹치지 않게 한다.
  function setLocked(locked) {
    boardLists().forEach(function (list) {
      var sortable = Sortable.get(list);
      if (sortable) {
        sortable.option("disabled", locked);
      }
    });
  }

  // 끄는 동안 목록 높이가 줄지 않게 고정한다. 카드가 원래 열을 떠나 그 열이 줄면, 위아래로 쌓인 배치(2×2, 1열)에서
  // 아래 행이 올라와 포인터가 놓으려던 열 밖에 놓인다(2026-10-15 QA). 늘어나는 것은 막지 않는다.
  // 카드를 누르는 순간(choose)에 잰다. 끌기 시작(start)은 다음 틱이라 그 전에 카드가 옮겨질 수 있다.
  function freezeHeights() {
    boardLists().forEach(function (list) {
      list.style.minHeight = list.getBoundingClientRect().height + "px";
    });
  }

  function releaseHeights() {
    boardLists().forEach(function (list) {
      list.style.minHeight = "";
    });
  }

  function filterProject() {
    var select = document.getElementById("filter-project");
    return select ? select.value : "";
  }

  // 카드가 아직 문서 안에 있으면 보드가 교체되지 않은 것(실패)이다. 원래 자리로 돌려놓는다.
  function restoreIfStillThere(event) {
    var item = event.item;
    if (item.isConnected) {
      var from = event.from;
      from.insertBefore(item, from.children[event.oldIndex] || null);
    }
    setLocked(false);
  }

  function moveCard(event) {
    if (event.from === event.to) {
      return;
    }
    var item = event.item;
    var restore = function () {
      restoreIfStillThere(event);
    };
    setLocked(true);
    var request;
    try {
      request = htmx.ajax("POST", "/tasks/" + item.dataset.taskId + "/status", {
        target: "#task-board",
        swap: "outerHTML",
        values: {
          status: event.to.dataset.status,
          version: item.dataset.version,
          project: filterProject(),
        },
      });
    } catch (error) {
      restore();
      return;
    }
    request.then(restore, restore);
  }

  function attach(list) {
    if (Sortable.get(list)) {
      return;
    }
    new Sortable(list, {
      group: "tasks",
      sort: false,
      animation: 150,
      delay: 150,
      delayOnTouchOnly: true,
      draggable: CARD_SELECTOR,
      ghostClass: "task-card--ghost",
      chosenClass: "task-card--chosen",
      // 열 밖(머리, 열 사이 틈 등)에 놓으면 원래 자리로 되돌린다. onEnd에서 from과 to가 같아 요청을 보내지 않는다.
      revertOnSpill: true,
      onChoose: freezeHeights,
      onUnchoose: releaseHeights,
      onEnd: moveCard,
    });
  }

  function init() {
    boardLists().forEach(attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // 보드가 교체되면(필터·상태 변경·이월) 새 목록에 다시 붙인다. 이미 붙은 목록은 건너뛴다.
  document.addEventListener("htmx:afterSettle", function (event) {
    var target = event.target;
    if (!target || !target.querySelector) {
      return;
    }
    if (target.id === "task-board" || target.querySelector(LIST_SELECTOR)) {
      init();
    }
  });
})();
