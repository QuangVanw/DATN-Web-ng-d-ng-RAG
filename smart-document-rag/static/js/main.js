document.querySelectorAll("[data-confirm-delete]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm("Bạn có chắc muốn xóa tài liệu này?")) {
      event.preventDefault();
    }
  });
});

const menuToggle = document.querySelector(".menu-toggle");
if (menuToggle) {
  const menu = document.getElementById(menuToggle.getAttribute("aria-controls"));
  const mobile = window.matchMedia("(max-width: 767px)");
  function updateMenu() {
    menuToggle.hidden = !mobile.matches;
    menuToggle.setAttribute("aria-expanded", String(!mobile.matches));
    menu.hidden = mobile.matches;
  }

  menuToggle.addEventListener("click", () => {
    menu.hidden = !menu.hidden;
    menuToggle.setAttribute("aria-expanded", String(!menu.hidden));
  });
  mobile.addEventListener("change", updateMenu);
  updateMenu();
}

const uploadForm = document.querySelector("[data-upload]");
if (uploadForm) {
  const input = uploadForm.querySelector('input[type="file"]');
  const fileList = uploadForm.querySelector("[data-file-list]");
  const status = uploadForm.querySelector("[data-upload-status]");
  input.addEventListener("change", () => {
    fileList.replaceChildren();
    for (const file of input.files) {
      const item = document.createElement("li");
      item.textContent = file.name;
      fileList.append(item);
    }
  });
  uploadForm.addEventListener("submit", () => {
    status.textContent = "Đang tải lên và đọc nội dung…";
    uploadForm.querySelector('button[type="submit"]').disabled = true;
  });
  window.addEventListener("pageshow", () => {
    status.textContent = "";
    uploadForm.querySelector('button[type="submit"]').disabled = false;
  });
}

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  const field = document.getElementById(button.getAttribute("aria-controls"));
  button.hidden = false;
  button.addEventListener("click", () => {
    const show = field.type === "password";
    field.type = show ? "text" : "password";
    button.setAttribute("aria-pressed", String(show));
    button.setAttribute("aria-label", show ? button.dataset.hideLabel : button.dataset.showLabel);
  });
});

const registrationForm = document.querySelector("[data-register]");
if (registrationForm) {
  const password = registrationForm.elements.password;
  const confirmation = registrationForm.elements.confirm_password;
  function validateConfirmation() {
    confirmation.setCustomValidity(
      confirmation.value && confirmation.value !== password.value ? "Mật khẩu xác nhận không khớp." : ""
    );
  }
  password.addEventListener("input", validateConfirmation);
  confirmation.addEventListener("input", validateConfirmation);
}
