(function () {
  localStorage.setItem("pc_onboarded", "1");
  sessionStorage.setItem("pc_onboarded", "1");
  const starter = "invoice-status-transition";
  const start = document.getElementById("start");
  if (!start) return;
  start.href = `/challenges/${starter}`;
  if (!InterviewAPI.isLoggedIn()) {
    start.href = `/login.html?next=/challenges/${starter}`;
    return;
  }
  ["obSignIn", "obJoin"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  });
  const browse = document.getElementById("obBrowse");
  if (browse) browse.hidden = false;
})();
