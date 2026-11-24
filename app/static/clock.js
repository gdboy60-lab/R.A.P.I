// 상단 시계 바: 1초마다 서버에 시계를 진행시키고 화면을 갱신한다.
// 화면이 닫히면 호출이 멈추므로 시계도 멈춘다 (서버가 한 번에 최대 5초만 인정).
(function () {
  const $ = (id) => document.getElementById(id);
  const SPEEDS = [1, 5, 10, 30];
  let state = null;

  function render(s) {
    if (!s || s.error) { if (s && s.error) alert(s.error); return; }
    state = s;
    $("clock-day").textContent = `${s.day}일차 / ${s.total_days}일 · ` +
      ({ pre_open: "장 시작 전", running: "장중", paused: "일시정지됨", closed: "장 마감" })[s.status];
    $("clock-time").textContent = s.time;
    $("btn-speed").textContent = `${s.speed}×`;
    $("btn-toggle").textContent = s.status === "paused" ? "▶" : "❚❚";
    $("btn-open").hidden = s.status !== "pre_open";
    $("btn-toggle").hidden = !["running", "paused"].includes(s.status);
    $("btn-speed").hidden = !["running", "paused"].includes(s.status);
    $("btn-skip").hidden = !["running", "paused"].includes(s.status);
    // 3주차: 장 마감이면 결과 화면으로 자동 전환. 지금은 버튼만 보여준다.
    $("btn-next").hidden = !(s.status === "closed" && !s.is_last_day);
  }

  async function call(method, path) {
    const r = await fetch(path, { method });
    render(await r.json());
  }

  $("btn-open").onclick = () => call("POST", "/api/clock/open");
  $("btn-toggle").onclick = () => call("POST", state.status === "paused" ? "/api/clock/resume" : "/api/clock/pause");
  $("btn-speed").onclick = () => {
    const next = SPEEDS[(SPEEDS.indexOf(state.speed) + 1) % SPEEDS.length];
    call("POST", `/api/clock/speed?speed=${next}`);
  };
  $("btn-skip").onclick = () => call("POST", "/api/clock/skip");
  $("btn-next").onclick = () => call("POST", "/api/clock/next");

  call("GET", "/api/clock");
  setInterval(() => { if (state && state.status === "running") call("GET", "/api/clock"); }, 1000);
})();
