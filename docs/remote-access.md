# Remote access: putting Filaments online

How the spare laptop serves Filaments at `https://myfilaments.dev` so Claude can use it from
any device. One-time setup; about 20 minutes. The code side is in `compose.yaml`,
`edge/Caddyfile` and `mcp_server/`.

```
 claude.ai / phone ──https──▶ myfilaments.dev (Cloudflare)
                                   │ tunnel: an outbound connection from the laptop
                                   ▼
 cloudflared ──▶ edge (allowlist) ──▶ mcp    /mcp, /.well-known/oauth-protected-resource/mcp
                                   └─▶ web    sign-in + OAuth: /accounts/login/, /o/authorize|token|revoke_token/,
                                              /.well-known/oauth-authorization-server
                                   everything else (/api/, /admin/, /o/introspect/) → 404
```

Nothing on your home network is opened: no router changes, and your home IP stays hidden.

## 1. On the laptop: account, clients and `.env`

```bash
cd ~/path/to/filaments_v2
git pull
docker compose up -d --build                                   # db + web
docker compose exec web python manage.py createsuperuser       # your account: pick a strong password
docker compose exec web python manage.py setup_oauth_clients   # prints two clients; shown ONCE
```

Save both printed client IDs and secrets in your password manager. Then set these in the
laptop's `.env` (see `.env.example` for the comments):

```bash
DJANGO_DEBUG=false
FILAMENTS_PUBLIC_URL=https://myfilaments.dev
FILAMENTS_INTROSPECTION_CLIENT_ID=<filaments-mcp-introspection client ID>
FILAMENTS_INTROSPECTION_CLIENT_SECRET=<its secret>
# FILAMENTS_ALLOW_INSECURE_PUBLIC_URL must NOT be set here.
```

Check the public surface locally before anything is online:

```bash
docker compose --profile remote up -d --build
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/health   # 404
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/admin/       # 404
curl -s http://127.0.0.1:8080/.well-known/oauth-authorization-server | head -c 80; echo
```

(With `FILAMENTS_PUBLIC_URL=https://myfilaments.dev`, the metadata names the public URL. That's
expected.)

## 2. In Cloudflare: create the tunnel

1. Open **dash.cloudflare.com** and choose **Zero Trust** in the left sidebar. The first
   time, pick a team name and the **Free** plan. It may ask for a card even at $0.
2. Go to **Networks → Tunnels → Create a tunnel**, choose **Cloudflared**, and name it
   `filaments`.
3. On the install page, choose **Docker** and copy the **token**: the long string after
   `--token` in the command it shows. Don't run that command; Compose runs `cloudflared`.
   Put the token in the laptop's `.env`:
   ```bash
   CLOUDFLARE_TUNNEL_TOKEN=<the token>
   ```
   Treat it like a password.
4. **Next** → **Public hostname**: leave Subdomain empty, Domain `myfilaments.dev`, Path
   empty, Service **HTTP** `edge:80`. Save.
5. Start everything, tunnel included:
   ```bash
   docker compose --profile public up -d --build
   ```
   The tunnel shows **Healthy** in the dashboard within a minute.

Check from any device:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://myfilaments.dev/api/health   # 404
curl -s -o /dev/null -w "%{http_code}\n" https://myfilaments.dev/mcp          # 401
```

## 3. In claude.ai: add the connector

1. **Settings → Connectors → Add custom connector.**
2. Name `Filaments`, URL `https://myfilaments.dev/mcp`.
3. Under the OAuth client options choose **Use your own OAuth client** and paste the
   **claude** client ID and secret from step 1.
4. Connect. Claude opens the Filaments sign-in page; sign in with your account.

The connector now works in every Claude app signed in to your account, phone included.
Try: "Save a note: test from the connector, tag it test." then "Find my notes tagged test."

## When something goes wrong

| Symptom | Likely cause |
|---|---|
| Connector setup says the redirect URL doesn't match | Claude may also use a `claude.com` callback. Add it to the `claude` client (Django admin → Applications) |
| "The notes server rejected my credentials" | The `FILAMENTS_API_TOKEN` in `.env` changed without restarting: `docker compose --profile public up -d` |
| Every tool call fails right after connecting | Introspection credentials in `.env` don't match: re-run `setup_oauth_clients --rotate`, update `.env` and Claude's connector |
| Tunnel shows Down | The laptop is off or offline, or the token is wrong: `docker compose logs cloudflared` |
| Locked out of sign-in | 10 failed attempts lock your address for 5 minutes |

To take Filaments offline: `docker compose --profile public stop cloudflared` (or delete the
tunnel in Cloudflare). To rotate the tunnel token: Cloudflare → the tunnel → **Refresh token**,
then update `.env` and restart.
