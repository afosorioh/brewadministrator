(() => {
  "use strict";

  const input = document.getElementById("raw-material-search");
  const results = document.getElementById("raw-material-results");
  const status = document.getElementById("raw-material-search-status");
  const config = window.rawMaterialSearchConfig;

  if (!input || !results || !status || !config) {
    return;
  }

  const initialRows = results.innerHTML;
  let debounceTimer = null;
  let activeRequest = null;
  let requestSequence = 0;

  const cancelPendingSearch = () => {
    window.clearTimeout(debounceTimer);
    debounceTimer = null;
    requestSequence += 1;

    if (activeRequest) {
      activeRequest.abort();
      activeRequest = null;
    }
  };

  const restoreInitialRows = (queryLength) => {
    cancelPendingSearch();
    results.innerHTML = initialRows;
    results.removeAttribute("aria-busy");
    status.textContent = queryLength > 0 ? config.minimumMessage : "";
  };

  const search = async (query, sequence) => {
    activeRequest = new AbortController();
    results.setAttribute("aria-busy", "true");
    status.textContent = config.loadingMessage;

    const url = new URL(config.url, window.location.href);
    url.searchParams.set("q", query);

    try {
      const response = await fetch(url, {
        headers: {Accept: "text/html"},
        signal: activeRequest.signal,
      });

      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }

      const html = await response.text();
      if (sequence !== requestSequence) {
        return;
      }

      results.innerHTML = html;
      status.textContent = "";
    } catch (error) {
      if (error.name !== "AbortError" && sequence === requestSequence) {
        status.textContent = config.errorMessage;
      }
    } finally {
      if (sequence === requestSequence) {
        results.removeAttribute("aria-busy");
        activeRequest = null;
      }
    }
  };

  input.addEventListener("input", () => {
    const query = input.value.trim();

    if (query.length < config.minimumLength) {
      restoreInitialRows(query.length);
      return;
    }

    cancelPendingSearch();
    const sequence = requestSequence;
    debounceTimer = window.setTimeout(() => search(query, sequence), 300);
  });
})();
