document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const password = document.getElementById(button.getAttribute("aria-controls"));
    if (!password) return;

    button.addEventListener("click", () => {
      const isVisible = password.type === "text";
      password.type = isVisible ? "password" : "text";
      button.textContent = isVisible ? "Show" : "Hide";
      button.setAttribute("aria-pressed", String(!isVisible));
    });
  });

  document.querySelectorAll("[data-officer-registration]").forEach((form) => {
    const village = form.querySelector("#officer-village");
    const district = form.querySelector("#officer-district");
    const faceCapture = form.querySelector('[name="face_capture"]');
    const camera = form.querySelector("[data-camera-capture]");
    if (village && district) {
      const updateDistrict = () => {
        district.value = village.selectedOptions[0]?.dataset.district || "";
      };
      village.addEventListener("change", updateDistrict);
      updateDistrict();
    }
    if (!camera || !faceCapture) return;

    const video = camera.querySelector("[data-camera-video]");
    const canvas = camera.querySelector("[data-camera-canvas]");
    const startButton = camera.querySelector("[data-camera-start]");
    const captureButton = camera.querySelector("[data-camera-capture-button]");
    const message = camera.querySelector("[data-camera-message]");
    let stream;

    const setMessage = (text, state = "") => {
      message.textContent = text;
      message.dataset.state = state;
    };
    const stopCamera = () => {
      stream?.getTracks().forEach((track) => track.stop());
      stream = undefined;
      video.srcObject = null;
      captureButton.disabled = true;
    };

    startButton.addEventListener("click", async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setMessage("Camera access is unavailable. Use HTTPS or localhost and a supported browser.", "error");
        return;
      }
      try {
        stopCamera();
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
        video.hidden = false;
        canvas.hidden = true;
        faceCapture.value = "";
        captureButton.disabled = false;
        setMessage("Camera is active. The captured image will be sent to the configured verification provider.");
      } catch (error) {
        setMessage(`Camera permission or device error: ${error.message}`, "error");
      }
    });

    captureButton.addEventListener("click", () => {
      if (!video.videoWidth || !video.videoHeight) {
        setMessage("Wait for the live camera preview before capturing.", "error");
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);
      const capturedImage = canvas.toDataURL("image/jpeg", 0.8);
      if (capturedImage.length > 1400000) {
        setMessage("The selfie image is too large. Please capture again.", "error");
        return;
      }
      stopCamera();
      video.hidden = true;
      canvas.hidden = false;
      faceCapture.value = capturedImage;
      setMessage("Selfie captured. The provider must verify your face and liveness; capture alone does not verify you.", "complete");
    });

    form.addEventListener("submit", (event) => {
      if (!faceCapture.value.startsWith("data:image/jpeg;base64,")) {
        event.preventDefault();
        setMessage("Capture a live selfie before submitting for provider verification.", "error");
        startButton.focus();
      }
    });
    window.addEventListener("pagehide", stopCamera);
  });

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
