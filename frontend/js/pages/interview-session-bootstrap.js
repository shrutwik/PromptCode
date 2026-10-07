// Start page data before the editor download/initialization, without claiming
// an editor lease or starting the timer until draft recovery is complete.
if (InterviewAPI.isLoggedIn()) {
  const id = location.pathname.split("/").filter(Boolean).pop();
  window.pcSessionBootstrap = Promise.all([
    InterviewAPI.getSession(id),
    InterviewAPI.listFiles(id),
    InterviewAPI.level(id).catch(() => null),
  ]).then(
    (data) => ({ data }),
    (error) => ({ error })
  );
}
