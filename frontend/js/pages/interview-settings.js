if (!InterviewAPI.requireAuth("/settings.html")) throw new Error("auth");
const status = document.getElementById("status");
const form = document.getElementById("form");
InterviewAPI.me().then((u) => {
  if (!u) { status.innerHTML = '<div class="pc-alert" data-tone="danger">Could not load profile.</div>'; return; }
  status.hidden = true;
  form.hidden = false;
  document.getElementById("display_name").value = u.display_name || u.username || "";
  document.getElementById("email").value = u.email || "";
});
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = form.querySelector('button[type="submit"]');
  btn.disabled = true;
  const display_name = document.getElementById("display_name").value.trim();
  try {
    const resp = await fetch("/api/auth/me", {
      method: "PUT",
      credentials: "include",
      headers: InterviewAPI.authHeaders(),
      body: JSON.stringify({ display_name }),
    });
    PCUI.toast(resp.ok ? "Saved" : "Save failed", { tone: resp.ok ? "success" : "danger" });
  } catch (err) {
    PCUI.toast(err.message || "Save failed", { tone: "danger" });
  } finally {
    btn.disabled = false;
  }
});
document.getElementById("logout").addEventListener("click", async () => {
  await InterviewAPI.logout();
  location.href = "/";
});
document.getElementById("copyFb").addEventListener("click", async () => {
  const text = document.getElementById("productFb").value.trim();
  const hint = document.getElementById("fbHint");
  if (!text) {
    hint.textContent = "Write a note first.";
    return;
  }
  try {
    await navigator.clipboard.writeText("[PromptCode beta feedback]\n" + text);
    hint.textContent = "Copied — paste into email or chat with the operator.";
    PCUI.toast("Feedback copied", { tone: "success" });
  } catch {
    hint.textContent = text;
  }
});
if (location.hash === "#feedback") {
  requestAnimationFrame(() => {
    const el = document.getElementById("feedback");
    el?.scrollIntoView({ block: "start" });
    el?.focus({ preventScroll: true });
  });
}
