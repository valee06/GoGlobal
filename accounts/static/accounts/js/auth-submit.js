(() => {
  document.querySelectorAll("form.auth-form").forEach((form) => {
    const button = form.querySelector("button[data-loading-label]");
    if (!button) return;

    const originalLabel = button.textContent.trim();
    let submitting = false;

    function restoreButton() {
      submitting = false;
      button.disabled = false;
      button.textContent = originalLabel;
      form.removeAttribute("aria-busy");
    }

    form.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;

      if (submitting) {
        event.preventDefault();
        return;
      }

      submitting = true;
      button.disabled = true;
      button.textContent = button.dataset.loadingLabel;
      form.setAttribute("aria-busy", "true");
    });

    window.addEventListener("pageshow", restoreButton);
  });
})();