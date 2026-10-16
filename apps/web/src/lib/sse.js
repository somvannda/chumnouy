// Minimal Server-Sent Events client.
//
// `EventSource` cannot send an Authorization header, so the console reads the
// stream with `fetch` + a ReadableStream instead. The parser is kept separate and
// pure so it can be unit-tested without a browser.

export function parseEvent(raw) {
  let name = "message";
  const data = [];
  for (const line of raw.split("\n")) {
    const text = line.replace(/\r$/, "");
    if (!text || text.startsWith(":")) continue; // blank line or heartbeat comment
    const separator = text.indexOf(":");
    const field = separator === -1 ? text : text.slice(0, separator);
    const value = separator === -1 ? "" : text.slice(separator + 1).replace(/^ /, "");
    if (field === "event") name = value;
    else if (field === "data") data.push(value);
  }
  if (!data.length) return null;
  let parsed = null;
  try {
    parsed = JSON.parse(data.join("\n"));
  } catch {
    parsed = null;
  }
  return { event: name, data: parsed };
}

export function createSseParser(onEvent) {
  let buffer = "";
  return {
    push(chunk) {
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      let index;
      while ((index = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        const event = parseEvent(raw);
        if (event) onEvent(event);
      }
    },
    flush() {
      const raw = buffer;
      buffer = "";
      const event = parseEvent(raw);
      if (event) onEvent(event);
    },
  };
}

export async function streamSse(url, { headers = {}, signal, onEvent } = {}) {
  const response = await fetch(url, {
    headers: { Accept: "text/event-stream", ...headers },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(response.statusText || "Stream failed");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser(onEvent);
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.flush();
}
