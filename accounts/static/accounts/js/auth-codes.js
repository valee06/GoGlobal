document.querySelectorAll("[data-resend-wait]").forEach((button) => {
  const seconds = Math.max(
    0,
    Number.parseInt(button.dataset.resendWait, 10) || 0
  );

  const deadline = Date.now() + seconds * 1000;

  const label = button.querySelector("[data-resend-label]");
  const counter = button.querySelector("[data-resend-counter]");

  let timer;

  function update() {
    const remaining = Math.max(
      0,
      Math.ceil((deadline - Date.now()) / 1000)
    );

    button.disabled = remaining > 0;
    label.textContent = button.dataset.readyLabel;

    counter.textContent = remaining > 0
      ? ` (${remaining} ${button.dataset.secondsLabel})`
      : "";

    if (remaining === 0 && timer !== undefined) {
      window.clearInterval(timer);
    }
  }

  update();

  if (seconds > 0) {
    timer = window.setInterval(update, 250);
  }

  window.addEventListener("pageshow", update);

  if (button.form) {
    button.form.addEventListener("submit", () => {
      if (timer !== undefined) {
        window.clearInterval(timer);
      }

      button.disabled = true;
      label.textContent = button.dataset.sendingLabel;
      counter.textContent = "";
    });
  }
});