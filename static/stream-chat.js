/**
 * Shared SSE chat streaming, used by the chat page (/chat/<id>) and the
 * new-chat page (/new_chat/stream).
 *
 * createStreamChat({
 *   form,           // <form> whose submit starts the stream
 *   streamUrl,      // endpoint answering with text/event-stream
 *   getContainer,   // () => scrollable messages container (bubbles appended here)
 *   getRedirectUrl, // optional ({convId, answer}) => URL to navigate to after "done"
 * })
 */
// Read an SSE response body, calling onEvent with each parsed
// "data: ..." payload. Comment lines (": keep-alive") are ignored.
async function readSseEvents(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of block.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch (_) {
          /* ignore malformed lines */
        }
      }
    }
  }
}

function createStreamChat({ form, streamUrl, getContainer, getRedirectUrl }) {
  if (!form) return;

  const textarea = form.querySelector('textarea[name="query"]');
  const button = form.querySelector('button[type="submit"]');

  let streaming = false;
  let chatContainer = null;

  const scrollBottom = () => {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
  };

  const appendUserBubble = (text) => {
    const wrap = document.createElement("div");
    wrap.className =
      "flex items-start gap-4 max-w-3xl mx-auto w-full justify-end";
    wrap.innerHTML = `
      <div class="bg-indigo-600 text-white rounded-2xl px-4 py-3 max-w-xl text-sm shadow-md"></div>
      <div class="w-8 h-8 rounded-full bg-indigo-700 flex items-center justify-center text-xs font-bold shrink-0">Ty</div>`;
    wrap.firstElementChild.textContent = text;
    chatContainer.appendChild(wrap);
  };

  const appendAiBubble = () => {
    const wrap = document.createElement("div");
    wrap.className = "flex items-start gap-4 max-w-3xl mx-auto w-full";
    wrap.innerHTML = `
      <div class="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold shrink-0 text-indigo-300">AI</div>
      <div class="bg-gray-800 border border-gray-700/60 text-gray-200 rounded-2xl px-5 py-4 max-w-2xl text-sm shadow-md space-y-2">
        <div class="stream-status text-xs text-gray-400 italic flex items-center gap-2">
          <span class="status-text">Agent myśli</span>
          <span class="flex items-center gap-1">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </span>
        </div>
        <div class="stream-content leading-relaxed whitespace-pre-wrap break-words"></div>
      </div>`;
    chatContainer.appendChild(wrap);
    scrollBottom();
    return {
      statusEl: wrap.querySelector(".stream-status"),
      statusText: wrap.querySelector(".status-text"),
      contentEl: wrap.querySelector(".stream-content"),
    };
  };

  const setBusy = (busy) => {
    button.disabled = busy;
    button.classList.toggle("opacity-50", busy);
    button.classList.toggle("cursor-not-allowed", busy);
    // NOTE: readOnly, not disabled — disabled inputs are excluded
    // from the form data.
    textarea.readOnly = busy;
    textarea.classList.toggle("opacity-60", busy);
  };

  // Fetch the stream and apply its events to the AI bubble appended by
  // the caller. Returns a redirect URL for the new-chat flow, or null.
  const streamAnswer = async (formData, { statusEl, statusText, contentEl }) => {
    const setStatus = (text) => (statusText.textContent = text);
    let raw = "";
    let convId = null;
    let finished = false;
    let renderQueued = false;
    let redirectUrl = null;

    // Throttle DOM updates to one per animation frame.
    const scheduleRender = () => {
      if (renderQueued) return;
      renderQueued = true;
      requestAnimationFrame(() => {
        renderQueued = false;
        // textContent is XSS-safe; markdown is rendered by the
        // server and arrives in the final "done" event.
        contentEl.textContent = raw;
        scrollBottom();
      });
    };

    const handleEvent = (data) => {
      switch (data.type) {
        case "start":
          convId = data.conv_id;
          break;
        case "token":
          raw += data.text;
          scheduleRender();
          break;
        case "status": {
          const d = data.detail ? ` — ${data.detail}` : "";
          setStatus(`🔧 ${data.tool}${d}`);
          break;
        }
        case "error":
          setStatus("⚠️ " + (data.text || "Błąd"));
          break;
        case "done":
          finished = true;
          // Swap in the server-rendered, sanitized HTML
          contentEl.classList.replace("whitespace-pre-wrap", "md-content");
          contentEl.innerHTML = data.html || "";
          statusEl.remove();
          scrollBottom();
          redirectUrl = getRedirectUrl?.({ convId, answer: data.answer });
          break;
      }
    };

    const response = await fetch(streamUrl, { method: "POST", body: formData });
    if (!response.ok || !response.body) {
      throw new Error("HTTP " + response.status);
    }
    await readSseEvents(response.body, handleEvent);

    // Stream ended without a done event — show what we got.
    if (!finished && raw) statusEl.remove();
    return redirectUrl;
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (streaming) return;
    const query = textarea.value.trim();
    if (!query) return;

    streaming = true;
    setBusy(true);
    chatContainer = getContainer ? getContainer() : chatContainer;
    // Snapshot BEFORE clearing the textarea.
    const formData = new FormData(form);

    appendUserBubble(query);
    textarea.value = "";
    const { statusEl, statusText, contentEl } = appendAiBubble();
    const setStatus = (text) => (statusText.textContent = text);

    let redirectUrl = null;
    try {
      redirectUrl = await streamAnswer(formData, { statusEl, statusText, contentEl });
    } catch (err) {
      setStatus("⚠️ Błąd połączenia: " + err.message);
    } finally {
      streaming = false;
      setBusy(false);
      textarea.focus();
      scrollBottom();
      // Give the user a moment to see the streamed answer, then go to
      // the persisted conversation page (new-chat flow only).
      if (redirectUrl) {
        setTimeout(() => {
          window.location.href = redirectUrl;
        }, 800);
      }
    }
  });

  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (textarea.value.trim()) {
        form.requestSubmit(); // fires the submit listener (unlike .submit())
      }
    }
  });
}
