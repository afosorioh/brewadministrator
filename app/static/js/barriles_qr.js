let qrScannerInstance = null;

function textoInterfaz(key, replacements = {}) {
  const translations = window.brewTranslations || {};
  let text = translations[key] || key;

  for (const [name, value] of Object.entries(replacements)) {
    text = text.replace(`__${name.toUpperCase()}__`, value);
  }

  return text;
}

function vibrarConfirmacion() {
  if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
}

function mostrarCodigoLeido(codigo, targetDisplayId = null) {
  if (!targetDisplayId) return;
  const el = document.getElementById(targetDisplayId);
  if (!el) return;
  el.textContent = textoInterfaz("codeRead", { code: codigo });
  el.classList.remove("d-none", "text-muted");
  el.classList.add("text-success", "fw-semibold");
}

function limpiarCodigoLeido(targetDisplayId = null) {
  if (!targetDisplayId) return;
  const el = document.getElementById(targetDisplayId);
  if (!el) return;
  el.textContent = "";
  el.classList.add("d-none");
  el.classList.remove("text-success", "fw-semibold");
}

function resaltarSelect(select) {
  if (!select) return;
  select.classList.add("border-success", "shadow-sm");
  setTimeout(() => select.classList.remove("border-success", "shadow-sm"), 2500);
}

function resaltarInput(input) {
  if (!input) return;
  input.classList.add("border-success", "shadow-sm");
  setTimeout(() => input.classList.remove("border-success", "shadow-sm"), 2500);
}

function cerrarScannerQR() {
  if (qrScannerInstance) {
    qrScannerInstance.stop()
      .then(() => qrScannerInstance.clear())
      .catch(() => {})
      .finally(() => { qrScannerInstance = null; });
  }
}

function abrirScannerQR({ targetInputId = null, targetSelectId = null, targetDisplayId = null }) {
  const modalEl = document.getElementById("qrScannerModal");
  const qrReaderId = "qr-reader";

  if (!modalEl) {
    alert(textoInterfaz("qrModalNotFound"));
    return;
  }

  limpiarCodigoLeido(targetDisplayId);
  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  function onScanSuccess(decodedText) {
    const codigo = decodedText.trim();
    mostrarCodigoLeido(codigo, targetDisplayId);
    vibrarConfirmacion();

    if (targetInputId) {
      const input = document.getElementById(targetInputId);
      if (input) {
        input.value = codigo;
        input.dispatchEvent(new Event("input"));
        resaltarInput(input);
      }
      cerrarScannerQR();
      modal.hide();
      return;
    }

    if (targetSelectId) {
      const select = document.getElementById(targetSelectId);
      if (select) {
        let encontrado = false;
        for (const option of select.options) {
          const codigoOption = (option.getAttribute("data-codigo") || "").trim();
          if (codigoOption.toUpperCase() === codigo.toUpperCase()) {
            select.value = option.value;
            select.dispatchEvent(new Event("change"));
            resaltarSelect(select);
            encontrado = true;
            break;
          }
        }
        if (!encontrado) {
          alert(textoInterfaz("kegNotFound", { code: codigo }));
          return;
        }
      }
    }

    cerrarScannerQR();
    modal.hide();
  }

  function onScanFailure(error) {
    // Los errores de lectura se ignoran mientras el escáner sigue activo.
  }

  qrScannerInstance = new Html5Qrcode(qrReaderId);
  Html5Qrcode.getCameras()
    .then(cameras => {
      if (!cameras || cameras.length === 0) {
        alert(textoInterfaz("noCamera"));
        return;
      }

      let cameraId = cameras[0].id;
      const backCam = cameras.find(c =>
        (c.label || "").toLowerCase().includes("back") ||
        (c.label || "").toLowerCase().includes("rear") ||
        (c.label || "").toLowerCase().includes("environment")
      );
      if (backCam) cameraId = backCam.id;

      qrScannerInstance.start(
        cameraId,
        { fps: 10, qrbox: { width: 250, height: 250 } },
        onScanSuccess,
        onScanFailure
      ).catch(err => {
        console.error("Camera start error:", err);
        alert(textoInterfaz("cameraStartError"));
      });
    })
    .catch(err => {
      console.error("Camera access error:", err);
      alert(textoInterfaz("cameraAccessError"));
    });

  modalEl.addEventListener("hidden.bs.modal", function onHidden() {
    cerrarScannerQR();
    modalEl.removeEventListener("hidden.bs.modal", onHidden);
  });
}
