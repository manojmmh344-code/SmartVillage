document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('form[data-password-confirm]').forEach((form) => {
    const password = form.querySelector('[name="password"], [name="new_password"]');
    const confirmation = form.querySelector('[name="confirm_password"]');
    if (!password || !confirmation) return;

    const validate = () => {
      confirmation.setCustomValidity(
        confirmation.value && password.value !== confirmation.value
          ? "Passwords do not match."
          : "",
      );
    };
    password.addEventListener("input", validate);
    confirmation.addEventListener("input", validate);
  });
});
