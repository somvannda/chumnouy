# @chumnouy/widget

A dependency-free, embeddable support launcher for the **public (requester)
surface**. Drop one `<script>` tag, hand it a requester portal token, and your end
user can open a ticket, read their own threads and reply — without a console
account.

It talks only to the public endpoints (`/v1/public/tickets`) with an
`X-Requester-Token` header, so the widget can never see another requester's
tickets or any internal note.

## Usage

```html
<script src="https://cdn.example.com/chumnouy-widget.js"></script>
<script>
  Chumnouy.init({
    token: "rqt_…",                        // required — portal token
    apiUrl: "https://api.chumnouy.chmaba.com", // omit for same-origin
    helpSlug: "acme-support",              // optional — enables help search
    title: "Support",
    label: "Support",
    accent: "#6957f5",
    position: "right",                     // or "left"
  });
</script>
```

Issue a token for a requester with:

```
POST /v1/requesters/{id}/portal-token     (scope: requesters:write)
```

The response contains the token **once**; pass it to the end user (server-rendered
into the page, or fetched with their session).

## Notes

- No build step and no dependencies — the file is the artifact.
- Styling is scoped (a `cmy-` prefix + one injected `<style>`); the accent is a
  CSS variable so it can be themed per integrator.
- With `helpSlug` set, the compose view offers a help-centre search that suggests
  articles (and lets the user read one) before they open a ticket.
- **Live chat**: the list view offers *Live chat*, which starts a session
  (`POST /v1/public/chat/sessions`) and then **streams** it over SSE
  (`/v1/public/chat/sessions/{id}/stream`) so agent replies appear immediately.
  Because `EventSource` cannot send the `X-Requester-Token` header, the stream is
  read with `fetch` + `TextDecoder`; browsers without those fall back to 3-second
  polling. The bounded stream reconnects when its window closes.
- **Branding**: the widget fetches `GET /v1/public/branding` on init and applies
  the workspace's title, launcher label, accent colour, position and greeting.
  Anything you pass to `init()` wins over the stored branding. With `pre_chat`
  enabled in the console, *Live chat* first asks "How can we help?" and sends that
  as the opening message.
- It is intentionally small: a launcher, a ticket list, a compose form and a
  thread with replies. Embedders who want the full experience should build their
  own UI on the public API.
