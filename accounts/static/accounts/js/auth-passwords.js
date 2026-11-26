(() => {
  document.querySelectorAll(".password-control").forEach((control) => {
    const input = control.querySelector("input");
    const button = control.querySelector(".password-toggle");

    if (!input || !button) return;

    button.hidden = false;

    button.addEventListener("click", () => {
      const visible = input.type === "password";

      input.type = visible ? "text" : "password";
      button.classList.toggle("is-visible", visible);

      button.setAttribute(
        "aria-label",
        visible ? button.dataset.hideLabel : button.dataset.showLabel
      );
    });
  });
})();