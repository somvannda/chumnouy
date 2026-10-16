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
  (`POST /v1/public/chat/sessions`) and polls it every few seconds for agent
  replies. Polling keeps the widget dependency-free; an SSE/WebSocket transport
  can replace it later without changing the API.
- It is intentionally small: a launcher, a ticket list, a compose form and a
  thread with replies. Embedders who want the full experience should build their
  own UI on the public API.
