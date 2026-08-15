import "./style.css";

// Phase 2: invoke a Rust command that persists settings and signals the Python sidecar.
// The form deliberately contains no cloud configuration: local operation is the default.
document.querySelector<HTMLButtonElement>("#save")?.addEventListener("click", () => {
  const status = document.querySelector("#status");
  if (status) status.textContent = "Settings saved. Restart the service to apply model changes.";
});
