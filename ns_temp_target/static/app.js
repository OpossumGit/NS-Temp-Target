const $ = id => document.getElementById(id), msg = $("msg");
function say(t, ok){ msg.textContent = t; msg.className = ok ? "ok" : "err"; }
async function post(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  return [r.ok, await r.json().catch(() => ({}))];
}
$("target").oninput = e => $("tv").textContent = Number(e.target.value).toFixed(1);
$("dur").oninput = e => $("dv").textContent = e.target.value;
async function unlock(){
  $("pin").disabled = true;
  const [ok, d] = await post("/login", {pin: $("pin").value});
  $("pin").disabled = false;
  if (ok){ $("pinbox").classList.add("hidden"); $("main").classList.remove("hidden"); say("", true); }
  else say(d.error || "Login failed", false);
  $("pin").value = "";
  if (!ok) $("pin").focus();
}
window.addEventListener("load", () => { if (!$("pinbox").classList.contains("hidden")) $("pin").focus(); });
$("pin").oninput = e => {
  e.target.value = e.target.value.replace(/\D/g, "");
  if (e.target.value.length === 4) unlock();
};
async function send(url, body, okText){
  $("submit").disabled = $("cancel").disabled = true; say("Sending...", true);
  const [ok, d] = await post(url, body);
  $("submit").disabled = $("cancel").disabled = false;
  if (ok) say(okText, true);
  else { say(d.error || "Failed", false); if (d.relogin){ $("main").classList.add("hidden"); $("pinbox").classList.remove("hidden"); } }
}
$("submit").onclick = () => send("/submit", {target: parseFloat($("target").value), duration: parseInt($("dur").value)}, "Temporary target set.");
$("cancel").onclick = () => send("/cancel", {}, "Temporary target cancelled.");
