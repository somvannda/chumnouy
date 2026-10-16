/*!
 * Chumnouy support widget — a dependency-free embeddable launcher.
 *
 * Integrators drop one script tag and call Chumnouy.init({ token }). The token is
 * a requester portal token (issued via POST /v1/requesters/{id}/portal-token), so
 * the widget only ever sees that requester's own public tickets.
 *
 *   <script src="https://cdn.example.com/chumnouy-widget.js"></script>
 *   <script>Chumnouy.init({ token: "rqt_…", apiUrl: "https://api.chumnouy.chmabacom" });</script>
 */
(function () {
  "use strict";

  var STYLE_ID = "chumnouy-widget-style";
  var CSS =
    ".cmy-btn{position:fixed;bottom:20px;z-index:2147483000;height:52px;padding:0 18px;border:0;border-radius:26px;" +
    "background:var(--cmy-accent,#6957f5);color:#fff;font:600 14px/1 system-ui,sans-serif;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.2)}" +
    ".cmy-btn:hover{filter:brightness(1.05)}" +
    ".cmy-panel{position:fixed;bottom:84px;z-index:2147483000;width:360px;max-width:calc(100vw - 32px);max-height:70vh;display:flex;" +
    "flex-direction:column;background:#fff;color:#191a1f;border-radius:16px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.25);" +
    "font:14px/1.45 system-ui,sans-serif}" +
    ".cmy-head{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--cmy-accent,#6957f5);color:#fff}" +
    ".cmy-head b{font-size:15px}.cmy-head button{background:none;border:0;color:#fff;font-size:18px;cursor:pointer;line-height:1}" +
    ".cmy-body{flex:1;overflow:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px}" +
    ".cmy-item{border:1px solid #e6e6ee;border-radius:12px;padding:10px 12px;cursor:pointer}" +
    ".cmy-item:hover{border-color:var(--cmy-accent,#6957f5)}" +
    ".cmy-item small{color:#6b6b78}.cmy-row{display:flex;gap:8px;align-items:center}" +
    ".cmy-input,.cmy-area{width:100%;box-sizing:border-box;border:1px solid #d6d6e0;border-radius:10px;padding:9px 11px;font:inherit;color:inherit}" +
    ".cmy-area{min-height:84px;resize:vertical}" +
    ".cmy-send{border:0;border-radius:10px;background:var(--cmy-accent,#6957f5);color:#fff;font:600 13px system-ui;padding:10px 14px;cursor:pointer}" +
    ".cmy-ghost{border:1px solid #d6d6e0;background:#fff;border-radius:10px;padding:8px 12px;font:600 13px system-ui;cursor:pointer}" +
    ".cmy-msg{border-radius:12px;padding:9px 12px;max-width:85%}" +
    ".cmy-msg.me{align-self:flex-end;background:var(--cmy-accent,#6957f5);color:#fff}" +
    ".cmy-msg.them{align-self:flex-start;background:#f1f1f6}" +
    ".cmy-err{color:#c0392b;font-size:13px}.cmy-empty{color:#6b6b78;text-align:center;padding:18px 0}";

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function init(options) {
    var opts = options || {};
    if (!opts.token) {
      console.error("[Chumnouy] init requires a requester portal token");
      return;
    }
    injectStyle();

    var apiUrl = (opts.apiUrl || "").replace(/\/$/, "");
    var token = opts.token;
    var helpSlug = opts.helpSlug || null;
    var pollTimer = null;
    var streamAbort = null;

    function clearPoll() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      if (streamAbort) {
        streamAbort.abort();
        streamAbort = null;
      }
    }
    var side = opts.position === "left" ? "left" : "right";
    var anchor = side + ":20px";
    var accent = opts.accent || "#6957f5";

    function request(path, init) {
      return fetch(apiUrl + "/api/v1" + path, {
        method: (init && init.method) || "GET",
        headers: Object.assign(
          { "X-Requester-Token": token },
          init && init.body ? { "Content-Type": "application/json" } : {}
        ),
        body: init && init.body ? JSON.stringify(init.body) : undefined,
      }).then(function (res) {
        return res.text().then(function (text) {
          var data = text ? JSON.parse(text) : null;
          if (!res.ok) {
            var message =
              (data && data.error && data.error.message) || res.statusText || "Request failed";
            throw new Error(message);
          }
          return data;
        });
      });
    }

    var launcher = el("button", "cmy-btn", opts.label || "Support");
    launcher.style.cssText = anchor;
    launcher.setAttribute("aria-label", opts.label || "Open support");

    var panel = el("div", "cmy-panel");
    panel.style.cssText = anchor;
    panel.style.display = "none";
    panel.style.setProperty("--cmy-accent", accent);

    var head = el("div", "cmy-head");
    var title = el("b", null, opts.title || "Support");
    var close = el("button", null, "×");
    close.setAttribute("aria-label", "Close");
    head.appendChild(title);
    head.appendChild(close);

    var body = el("div", "cmy-body");
    panel.appendChild(head);
    panel.appendChild(body);
    document.body.appendChild(launcher);
    document.body.appendChild(panel);

    var brandingGreeting = null;
    var preChat = false;

    function applyBranding(branding) {
      var b = branding || {};
      if (!opts.title && b.title) opts.title = b.title;
      if (!opts.label && b.label) opts.label = b.label;
      if (!opts.accent && b.accent) {
        accent = b.accent;
        panel.style.setProperty("--cmy-accent", accent);
      }
      if (!opts.position && b.position === "left") {
        anchor = "left:20px";
        launcher.style.cssText = anchor;
        panel.style.cssText = anchor;
      }
      brandingGreeting = b.greeting || null;
      preChat = !!b.pre_chat;
      title.textContent = opts.title || "Support";
      launcher.textContent = opts.label || "Support";
      launcher.setAttribute("aria-label", opts.label || "Open support");
    }

    request("/public/branding")
      .then(applyBranding)
      .catch(function () {
        /* branding is optional — fall back to the options passed to init */
      });

    function show(visible) {
      panel.style.display = visible ? "flex" : "none";
      if (visible) renderList();
    }

    function setError(message) {
      var existing = body.querySelector(".cmy-err");
      if (existing) existing.remove();
      if (message) body.appendChild(el("div", "cmy-err", message));
    }

    function renderList() {
      clearPoll();
      body.innerHTML = "";
      if (brandingGreeting) body.appendChild(el("div", "cmy-empty", brandingGreeting));
      var chatBtn = el("button", "cmy-ghost", "Live chat");
      chatBtn.onclick = startChat;
      body.appendChild(chatBtn);
      var newBtn = el("button", "cmy-ghost", "New request");
      newBtn.onclick = renderCompose;
      body.appendChild(newBtn);
      request("/public/tickets?limit=50")
        .then(function (data) {
          var tickets = (data && data.data) || [];
          if (!tickets.length) {
            body.appendChild(el("div", "cmy-empty", "No requests yet."));
            return;
          }
          tickets.forEach(function (ticket) {
            var item = el("div", "cmy-item");
            item.appendChild(el("div", null, ticket.subject));
            var meta = el("small", null, ticket.reference + " · " + ticket.status);
            item.appendChild(meta);
            item.onclick = function () {
              renderThread(ticket.id);
            };
            body.appendChild(item);
          });
        })
        .catch(function (err) {
          setError(err.message);
        });
    }

    function streamChat(sessionId, refresh) {
      if (typeof TextDecoder === "undefined" || typeof AbortController === "undefined") {
        // No streaming in this browser: fall back to polling.
        pollTimer = setInterval(refresh, 3000);
        return;
      }
      var controller = new AbortController();
      streamAbort = controller;

      function parseEvent(raw) {
        var name = "message";
        var data = [];
        raw.split("\n").forEach(function (line) {
          var text = line.replace(/\r$/, "");
          if (!text || text.charAt(0) === ":") return; // blank line or heartbeat
          var separator = text.indexOf(":");
          var field = separator === -1 ? text : text.slice(0, separator);
          var value = separator === -1 ? "" : text.slice(separator + 1).replace(/^ /, "");
          if (field === "event") name = value;
          else if (field === "data") data.push(value);
        });
        return data.length ? { event: name, data: data.join("\n") } : null;
      }

      function once() {
        return fetch(apiUrl + "/api/v1/public/chat/sessions/" + sessionId + "/stream?timeout=25", {
          headers: { "X-Requester-Token": token, Accept: "text/event-stream" },
          signal: controller.signal,
        }).then(function (res) {
          if (!res.ok || !res.body) throw new Error("stream failed");
          var reader = res.body.getReader();
          var decoder = new TextDecoder();
          var buffer = "";
          function pump() {
            return reader.read().then(function (result) {
              if (result.done) return null;
              buffer = (buffer + decoder.decode(result.value, { stream: true })).replace(/\r\n/g, "\n");
              var index;
              while ((index = buffer.indexOf("\n\n")) !== -1) {
                var event = parseEvent(buffer.slice(0, index));
                buffer = buffer.slice(index + 2);
                if (event && event.event === "message") refresh();
              }
              return pump();
            });
          }
          return pump();
        });
      }

      function loop() {
        once()
          .catch(function () {
            /* a dropped stream is not fatal — we reconnect below */
          })
          .then(function () {
            if (!controller.signal.aborted) setTimeout(loop, 1500);
          });
      }
      loop();
    }

    function startChat() {
      if (preChat) {
        renderChatStart();
        return;
      }
      request("/public/chat/sessions", { method: "POST" })
        .then(function (session) {
          renderChat(session.id);
        })
        .catch(function (err) {
          setError(err.message);
        });
    }

    function renderChatStart() {
      clearPoll();
      body.innerHTML = "";
      if (brandingGreeting) body.appendChild(el("div", "cmy-empty", brandingGreeting));
      var msg = el("textarea", "cmy-area");
      msg.placeholder = "How can we help?";
      var start = el("button", "cmy-send", "Start chat");
      var back = el("button", "cmy-ghost", "Back");
      back.onclick = renderList;
      var row = el("div", "cmy-row");
      row.appendChild(start);
      row.appendChild(back);
      body.appendChild(msg);
      body.appendChild(row);
      start.onclick = function () {
        setError(null);
        request("/public/chat/sessions", { method: "POST" })
          .then(function (session) {
            var text = (msg.value || "").trim();
            if (!text) {
              renderChat(session.id);
              return null;
            }
            return request("/public/chat/sessions/" + session.id + "/messages", {
              method: "POST",
              body: { body: text },
            }).then(function () {
              renderChat(session.id);
            });
          })
          .catch(function (err) {
            setError(err.message);
          });
      };
    }

    function renderChat(sessionId) {
      clearPoll();
      body.innerHTML = "";
      var stream = el("div", null);
      var reply = el("textarea", "cmy-area");
      reply.placeholder = "Message…";
      var send = el("button", "cmy-send", "Send");
      var back = el("button", "cmy-ghost", "Back");
      back.onclick = function () {
        title.textContent = opts.title || "Support";
        renderList();
      };
      var row = el("div", "cmy-row");
      row.appendChild(send);
      row.appendChild(back);
      body.appendChild(stream);
      body.appendChild(reply);
      body.appendChild(row);
      function draw() {
        request("/public/chat/sessions/" + sessionId)
          .then(function (session) {
            stream.innerHTML = "";
            (session.messages || []).forEach(function (m) {
              var bubble = el("div", "cmy-msg " + (m.author_type === "requester" ? "me" : "them"));
              bubble.textContent = m.body;
              stream.appendChild(bubble);
            });
            body.scrollTop = body.scrollHeight;
          })
          .catch(function () {
            /* polling is best-effort */
          });
      }
      send.onclick = function () {
        setError(null);
        request("/public/chat/sessions/" + sessionId + "/messages", {
          method: "POST",
          body: { body: reply.value },
        })
          .then(function () {
            reply.value = "";
            draw();
          })
          .catch(function (err) {
            setError(err.message);
          });
      };
      draw();
      streamChat(sessionId, draw);
    }

    function renderArticle(articleSlug) {
      clearPoll();
      body.innerHTML = "";
      request("/public/help/" + encodeURIComponent(helpSlug) + "/articles/" + encodeURIComponent(articleSlug))
        .then(function (article) {
          title.textContent = article.title;
          body.appendChild(el("div", "cmy-msg them", article.body));
          var back = el("button", "cmy-ghost", "Back");
          back.onclick = function () {
            title.textContent = opts.title || "Support";
            renderCompose();
          };
          body.appendChild(back);
        })
        .catch(function (err) {
          setError(err.message);
        });
    }

    function renderCompose() {
      clearPoll();
      body.innerHTML = "";
      // Optional help-centre search: suggest articles before opening a ticket.
      if (helpSlug) {
        var search = el("input", "cmy-input");
        search.placeholder = "Search help…";
        var results = el("div", null);
        search.oninput = function () {
          var term = search.value.trim();
          results.innerHTML = "";
          if (!term) return;
          request("/public/help/" + encodeURIComponent(helpSlug) + "?q=" + encodeURIComponent(term))
            .then(function (data) {
              (data.articles || []).slice(0, 5).forEach(function (article) {
                var item = el("div", "cmy-item");
                item.appendChild(el("div", null, article.title));
                item.onclick = function () {
                  renderArticle(article.slug);
                };
                results.appendChild(item);
              });
            })
            .catch(function () {
              /* suggestions are best-effort */
            });
        };
        body.appendChild(search);
        body.appendChild(results);
      }
      var subject = el("input", "cmy-input");
      subject.placeholder = "Subject";
      var message = el("textarea", "cmy-area");
      message.placeholder = "How can we help?";
      var send = el("button", "cmy-send", "Send");
      var back = el("button", "cmy-ghost", "Back");
      back.onclick = renderList;
      var row = el("div", "cmy-row");
      row.appendChild(send);
      row.appendChild(back);
      body.appendChild(subject);
      body.appendChild(message);
      body.appendChild(row);
      send.onclick = function () {
        setError(null);
        request("/public/tickets", {
          method: "POST",
          body: { subject: subject.value, message: message.value },
        })
          .then(function (ticket) {
            renderThread(ticket.id);
          })
          .catch(function (err) {
            setError(err.message);
          });
      };
    }

    function renderThread(ticketId) {
      clearPoll();
      body.innerHTML = "";
      request("/public/tickets/" + ticketId)
        .then(function (ticket) {
          title.textContent = ticket.reference;
          (ticket.messages || []).forEach(function (m) {
            var bubble = el("div", "cmy-msg " + (m.author_type === "requester" ? "me" : "them"));
            bubble.textContent = m.body;
            body.appendChild(bubble);
          });
          var reply = el("textarea", "cmy-area");
          reply.placeholder = "Reply…";
          var send = el("button", "cmy-send", "Reply");
          var back = el("button", "cmy-ghost", "Back");
          back.onclick = function () {
            title.textContent = opts.title || "Support";
            renderList();
          };
          var row = el("div", "cmy-row");
          row.appendChild(send);
          row.appendChild(back);
          body.appendChild(reply);
          body.appendChild(row);
          send.onclick = function () {
            setError(null);
            request("/public/tickets/" + ticketId + "/messages", {
              method: "POST",
              body: { body: reply.value },
            })
              .then(function () {
                renderThread(ticketId);
              })
              .catch(function (err) {
                setError(err.message);
              });
          };
        })
        .catch(function (err) {
          setError(err.message);
        });
    }

    launcher.onclick = function () {
      show(panel.style.display === "none");
    };
    close.onclick = function () {
      show(false);
    };
  }

  window.Chumnouy = { init: init };
})();
