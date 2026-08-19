(() => {
  "use strict";

  const PAYLOAD_EVENT = "GoreeCloudCapturePayload";
  const RESULT_EVENT = "GoreeCloudCaptureResult";
  const form = document.getElementById("browser-capture-form");
  const waiting = document.getElementById("browser-capture-waiting");
  const result = document.getElementById("browser-capture-result");
  const kindInput = document.getElementById("browser-capture-kind");
  const sourceInput = document.getElementById("browser-capture-source");
  const titleInput = document.getElementById("browser-capture-title");
  const descriptionInput = document.getElementById("browser-capture-description");
  const saveButton = document.getElementById("browser-capture-save");
  const cancelButton = document.getElementById("browser-capture-cancel");
  const csrfInput = form?.querySelector("input[name=csrfmiddlewaretoken]");

  if (
    !form ||
    !waiting ||
    !result ||
    !kindInput ||
    !sourceInput ||
    !titleInput ||
    !descriptionInput ||
    !saveButton ||
    !cancelButton ||
    !csrfInput
  ) {
    return;
  }

  let payloadReceived = false;
  let completed = false;

  function notifyBrowser(status) {
    if (completed) {
      return;
    }
    completed = true;
    document.dispatchEvent(
      new CustomEvent(RESULT_EVENT, {
        bubbles: false,
        cancelable: false,
        detail: { status },
      })
    );
  }

  function showResult(message, isError = false) {
    result.hidden = false;
    result.textContent = message;
    result.classList.toggle("text-error", isError);
  }

  function cleanSourceURL(payload, kind) {
    const candidate = kind === "link" ? payload.linkUrl : payload.pageUrl || payload.linkUrl;
    const value = String(candidate || "").trim();
    return /^https?:\/\//i.test(value) ? value.slice(0, 8192) : "";
  }

  function initialTitle(payload, kind, selectedText, sourceURL) {
    if (kind === "selection") {
      const firstLine = selectedText
        .split(/\r?\n/)
        .map(line => line.trim())
        .find(Boolean);
      if (firstLine) {
        return firstLine.slice(0, 500);
      }
    }
    const provided = String(payload.title || "").trim();
    return (provided || sourceURL || "New task").slice(0, 500);
  }

  function initialDescription(kind, selectedText, sourceURL) {
    const parts = [];
    if (kind === "selection" && selectedText) {
      parts.push(selectedText.slice(0, 7600));
    }
    if (sourceURL) {
      parts.push(`Source: ${sourceURL}`);
    }
    return parts.join("\n\n").slice(0, 8192);
  }

  document.addEventListener(
    PAYLOAD_EVENT,
    event => {
      if (payloadReceived || completed) {
        return;
      }

      const payload = event.detail;
      if (!payload || payload.destination !== "task") {
        showResult("The Browser handoff could not be verified.", true);
        notifyBrowser("error");
        return;
      }

      const kind = payload.kind === "selection" ? "selection" : payload.kind === "link" ? "link" : "";
      if (!kind) {
        showResult("The Browser provided an unsupported task capture type.", true);
        notifyBrowser("error");
        return;
      }

      const selectedText = String(payload.text || "").trim();
      const sourceURL = cleanSourceURL(payload, kind);
      if (kind === "link" && !sourceURL) {
        showResult("The Browser did not provide a valid web link.", true);
        notifyBrowser("error");
        return;
      }

      payloadReceived = true;
      kindInput.value = kind;
      sourceInput.value = sourceURL;
      titleInput.value = initialTitle(payload, kind, selectedText, sourceURL);
      descriptionInput.value = initialDescription(kind, selectedText, sourceURL);
      waiting.hidden = true;
      form.hidden = false;
      titleInput.focus();
    },
    { once: true }
  );

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!payloadReceived || completed || !titleInput.value.trim()) {
      return;
    }

    saveButton.disabled = true;
    cancelButton.disabled = true;
    showResult("Saving task…");

    try {
      const response = await fetch(window.location.pathname, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfInput.value,
          Accept: "application/json",
        },
        body: JSON.stringify({
          kind: kindInput.value,
          title: titleInput.value,
          description: descriptionInput.value,
          source_url: sourceInput.value,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.ok !== true || !data.task_id) {
        throw new Error("task save rejected");
      }

      form.hidden = true;
      showResult("Saved to GoreeCloud Tasks.");
      notifyBrowser("saved");
    } catch {
      saveButton.disabled = false;
      cancelButton.disabled = false;
      showResult("GoreeCloud Tasks could not save this task. Review the fields and try again.", true);
    }
  });

  cancelButton.addEventListener("click", () => {
    form.hidden = true;
    showResult("Capture cancelled. You can close this tab.");
    notifyBrowser("cancelled");
  });
})();
