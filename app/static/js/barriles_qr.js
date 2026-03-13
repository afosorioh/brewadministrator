let qrScannerInstance = null;

function vibrarConfirmacion() {
  if (navigator.vibrate) {
    navigator.vibrate([120, 60, 120]);
  }
}

function mostrarCodigoLeido(codigo, targetDisplayId = null) {
  if (!targetDisplayId) return;

  const el = document.getElementById(targetDisplayId);
  if (!el) return;

  el.textContent = `Código leído: ${codigo}`;
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
  setTimeout(() => {
    select.classList.remove("border-success", "shadow-sm");
  }, 2500);
}

function resaltarInput(input) {
  if (!input) return;

  input.classList.add("border-success", "shadow-sm");
  setTimeout(() => {
    input.classList.remove("border-success", "shadow-sm");
  }, 2500);
}

function cerrarScannerQR() {
  if (qrScannerInstance) {
    qrScannerInstance.stop()
      .then(() => qrScannerInstance.clear())
      .catch(() => {})
      .finally(() => {
        qrScannerInstance = null;
      });
  }
}

function abrirScannerQR({
  targetInputId = null,
  targetSelectId = null,
  targetDisplayId = null
}) {
  const modalEl = document.getElementById("qrScannerModal");
  const qrReaderId = "qr-reader";

  if (!modalEl) {
    alert("No se encontró el modal del escáner QR.");
    return;
  }

  limpiarCodigoLeido(targetDisplayId);

  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  function onScanSuccess(decodedText) {
    const codigo = decodedText.trim();
    mostrarCodigoLeido(codigo, targetDisplayId);
    vibrarConfirmacion();

    // Caso 1: llenar input directamente
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

    // Caso 2: buscar en select por data-codigo
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
          alert(`No se encontró un barril con código: ${codigo}`);
          return;
        }
      }
    }

    cerrarScannerQR();
    modal.hide();
  }

  function onScanFailure(error) {
    // silencioso
  }

  qrScannerInstance = new Html5Qrcode(qrReaderId);

  Html5Qrcode.getCameras()
    .then(cameras => {
      if (!cameras || cameras.length === 0) {
        alert("No se detectó ninguna cámara.");
        return;
      }

      let cameraId = cameras[0].id;

      const backCam = cameras.find(c =>
        (c.label || "").toLowerCase().includes("back") ||
        (c.label || "").toLowerCase().includes("rear") ||
        (c.label || "").toLowerCase().includes("environment")
      );

      if (backCam) {
        cameraId = backCam.id;
      }

      qrScannerInstance.start(
        cameraId,
        {
          fps: 10,
          qrbox: { width: 250, height: 250 }
        },
        onScanSuccess,
        onScanFailure
      ).catch(err => {
        console.error("Error iniciando cámara:", err);
        alert("No fue posible iniciar la cámara.");
      });
    })
    .catch(err => {
      console.error("Error obteniendo cámaras:", err);
      alert("No fue posible acceder a la cámara.");
    });

  modalEl.addEventListener("hidden.bs.modal", function onHidden() {
    cerrarScannerQR();
    modalEl.removeEventListener("hidden.bs.modal", onHidden);
  });
}