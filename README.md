# Sisyphus BBS

A bulletin board system for the web: discussion boards, real-time chat with
direct messages, a file area, and games. Python, FastAPI, SQLite, server-rendered
pages, and a terminal look. One process, one database file, no build step.

> "One must imagine Sisyphus happy." — Camus

This file is the operator's manual: how to run it, every setting, and the things
that are easy to forget after time away. Design documents live in [`docs/`](docs/).

There are two ways to run it, and most of this manual is split along that line:

- **Locally**, on your own machine, for development or a private board on a
  LAN: `sisyphus.sh` starts and stops it, and it serves HTTPS itself if you give
  it a certificate. See *Running locally*.
- **Live on a server**, for the public: a systemd service behind nginx with a
  Let's Encrypt certificate, all set up by one script. See *Running on a server*.
  `sisyphus.sh` is not used there.

Everything after those two sections (settings, roles, resetting, backups,
limits, games) applies to both, with the differences called out.

---

## Running locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

./sisyphus.sh start        # then open http://localhost:8000 (https:// once you add a certificate, see TLS)
```

Needs Python 3.12 or newer. `requirements.txt` pins the exact versions the test
suite passes against; `pyproject.toml` holds the minimum supported versions.

**The first account registered becomes the superadmin.** Register yours before
telling anyone the address, or make it first from the command line:

```sh
.venv/bin/python admin/create_superadmin.py yourname     # asks for a password
```

| Command | What it does |
|---|---|
| `./sisyphus.sh start` | Start in the background. Logs to `log/sisyphus.log`. |
| `./sisyphus.sh stop` | Stop it. |
| `./sisyphus.sh restart` | Both. |
| `./sisyphus.sh status` | Is it running, and on which port. |

The script uses `.venv/bin/python` when it exists, otherwise `python3`. It finds
the running server by its port, and it reads `SISYPHUS_WEB_PORT` from your
*shell*, not from `.env`; if you change the port in `.env`, also export it in the
shell you run the script from, or `status` and `stop` will look in the wrong place.

A local board listens on every interface by default, so anyone on your network
can reach it. Set `SISYPHUS_WEB_HOST=127.0.0.1` to keep it to this machine.

## Running on a server

`deploy/install-debian.sh` puts the whole thing on a Debian 13 machine behind
nginx with a Let's Encrypt certificate, and is also how you update it later.

**Before you run it:** DNS for the domain must already point at the server, and
ports 80 and 443 must be reachable from the internet, including through any
firewall your hosting provider puts in front of the machine (port 80 is needed
for the certificate challenge and then only redirects to https). You need a user
with sudo.

```sh
git clone https://github.com/tedfiedler/sisyphus-bbs.git
cd sisyphus-bbs
sudo ./deploy/install-debian.sh --domain bbs.example.org --email you@example.org --admin yourname --tz America/Chicago
```

The password for the admin account is asked for on the terminal. That clone is
only there to supply the script: the installer makes its own checkout in
`/opt/sisyphus`, owned by a `sisyphus` system user that the service runs as.

What it sets up:

- the code in `/opt/sisyphus` with a virtualenv, and `.env` with a fresh secret,
  the board bound to `127.0.0.1` behind the proxy, `SISYPHUS_TRUST_PROXY=1`, and
  registration **invite-only** (pass `--open` to leave it open);
- the superadmin account, made before the site is reachable (`--admin`); without
  it, the first person to register gets the board;
- a locked-down systemd service, `sisyphus`, that restarts on failure and at boot;
- nginx on 443 (TLS 1.2/1.3 only, HTTP/2, the chat WebSocket) with port 80
  serving the certificate challenge and redirecting everything else to https;
- the Let's Encrypt certificate, renewed twice a day from cron with nginx
  reloaded when a new one lands;
- ufw allowing only SSH, 80 and 443; fail2ban for sshd and for repeated failed
  logins to the board;
- log rotation, a nightly backup, unattended security upgrades, and the
  `sisyphus-update` command.

Options worth knowing (`--help` lists them all): `--name "Board name"`,
`--tz ZONE` for the game day, `--self-signed` for a machine without public DNS
yet, `--staging` to rehearse without spending Let's Encrypt rate limits,
`--no-firewall` if you manage the firewall yourself, and `--deploy-key FILE` if
you deploy from a private fork.

### Day to day on the server

| Task | How |
|---|---|
| Update to the latest `main` | `sudo sisyphus-update` (pulls, installs dependencies, restarts, shows status) |
| Restart | `sudo systemctl restart sisyphus` |
| Is it running, what is it saying | `systemctl status sisyphus`, `sudo journalctl -u sisyphus -f` |
| Application log | `/opt/sisyphus/log/sisyphus.log` (rotated weekly) |
| nginx logs | `/var/log/nginx/sisyphus.access.log`, `sisyphus.error.log` |
| Change a setting | `sudo -e /opt/sisyphus/.env` (the directory is private to the `sisyphus` user), then restart |
| Backups | `/var/backups/sisyphus`, nightly at 04:10, 14 days kept. **Copy them off the machine**; the script only makes them. |
| Certificate | `sudo certbot certificates`; renewal runs from `/etc/cron.d/sisyphus-certbot` |
| Who is banned | `sudo fail2ban-client status sisyphus-login` |
| Firewall | `sudo ufw status` |

**Do not use `sisyphus.sh` on the server.** systemd owns the process there; the
script would stop the managed process (which systemd restarts at once) and start
a second copy outside systemd that cannot bind the port. Nothing breaks, but it
is confusing.

Re-run the install script when the deployment itself changes (the nginx site,
the service unit, the jails); it keeps `.env`, the database, uploads and a
certificate that is still good, and reports that the admin account already
exists. The copy of the script in your home-directory clone does not update
itself: `git pull` there first, or run the one in `/opt/sisyphus/deploy/`.

An uptime monitor can watch `https://your.host/` with GET or HEAD; both answer
200.

## When to restart, and what it costs

| You changed | Restart? |
|---|---|
| Anything in `lib/` or `src/` (Python) | **Yes.** |
| `.env` or an environment variable | **Yes.** Settings are read once, at startup. |
| A template (`frontend/templates/`) or anything in `frontend/static/` | No. They are read from disk on each request, and asset URLs carry a version stamp so browsers fetch the new file. |
| The database schema | Restart; migrations run automatically at startup. |

Locally that is `./sisyphus.sh restart`; on the server `sudo systemctl restart
sisyphus`, or `sudo sisyphus-update`, which restarts as part of updating.

What a restart costs: every Mille Bornes game in progress is lost (they live in
memory). Logins, boards, chat history, and *The Long Climb* characters are all in
the database and survive.

## Settings

Every setting is an environment variable. Put them in a file named **`.env`** in
the project root (`/opt/sisyphus/.env` on a server), one `NAME=value` per line;
it is loaded automatically at startup and is listed in `.gitignore`, so it is
never committed. Keep it that way: it holds your secret key. The deploy script
writes a complete `.env` for you; locally you write it yourself.

```sh
# .env
SISYPHUS_SECRET=...            # see below
SISYPHUS_NAME=Sisyphus BBS
```

| Variable | Default | What it is for |
|---|---|---|
| `SISYPHUS_SECRET` | a public placeholder | **Set this.** See the next section. |
| `SISYPHUS_NAME` | `Sisyphus BBS` | The name shown in the header and page titles. |
| `SISYPHUS_WEB_HOST` | `0.0.0.0` | Address to listen on. `127.0.0.1` makes it reachable from this machine only (what the deploy script sets, since nginx is in front). |
| `SISYPHUS_WEB_PORT` | `8000` | Port to listen on. |
| `SISYPHUS_DB` | `db/sisyphus.db` | The SQLite database file. |
| `SISYPHUS_FILES` | `file_store/` | Where uploaded files are kept. |
| `SISYPHUS_SESSION_HOURS` | `24` | How long a login lasts. |
| `SISYPHUS_INVITE_ONLY` | off | Set to `1` and nobody registers without an invitation code. See Invitations. |
| `SISYPHUS_TZ` | the server's zone | IANA zone (e.g. `America/Chicago`) that decides when a game day turns over in *The Long Climb*. A server's zone is usually UTC, so set this. |
| `SISYPHUS_SSL_CERT` | `certs/cert.pem` | TLS certificate, for a board serving HTTPS itself. See TLS below. |
| `SISYPHUS_SSL_KEY` | `certs/key.pem` | TLS private key. |
| `SISYPHUS_TRUST_PROXY` | off | Set to `1` **only** behind a reverse proxy you control. See below. |
| `SISYPHUS_ALLOWED_ORIGINS` | none | Extra origins allowed to open the chat WebSocket. See below. |

### `SISYPHUS_SECRET`: what it is and why to set it

It has exactly one job today: it is the key for **CSRF tokens**. Every form on
the site carries a hidden token; the server computes it as an HMAC of your
session token, keyed with this secret, and recomputes it when the form comes
back. That is how it knows a form came from its own page rather than from some
other site acting in your name. Nothing is stored; the token can always be
recomputed.

Leaving it at the default is not an emergency — forging a token also needs the
visitor's session token, which sits in an `HttpOnly` cookie another site cannot
read — but the default is a known value in a public repository, and anything
added later that signs things (reset links, "remember me") would inherit it.
The server logs a warning at startup until it is set.

Generate one:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put it in `.env` as `SISYPHUS_SECRET=<that value>`, make the file private
(`chmod 600 .env`), and restart. Pages open at the time hold tokens made with the
old key; a reload fixes them.

**Changing it later** is safe and logs nobody out (sessions do not depend on
it); it only invalidates forms that were already open.

### TLS

This is for a board that serves HTTPS itself, which is the local case. On a
server set up by the deploy script, nginx terminates TLS with the Let's Encrypt
certificate and talks plain HTTP to the board on localhost; leave these unset
there.

If both `certs/cert.pem` and `certs/key.pem` exist, the board speaks HTTPS;
otherwise plain HTTP. For a self-signed certificate, good enough for a private
board:

```sh
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout certs/key.pem -out certs/cert.pem -subj "/CN=localhost"
```

`certs/` is in `.gitignore`. Over HTTPS the session cookie is marked `Secure`
and an HSTS header is sent.

### Behind a reverse proxy

The deploy script does all of this. If you put nginx, Caddy, or similar in
front yourself:

- Set `SISYPHUS_TRUST_PROXY=1`. The board then believes `X-Forwarded-For` (so
  rate limits apply per visitor rather than to the proxy) and
  `X-Forwarded-Proto` (so cookies are still marked `Secure`). **Never set it
  without a proxy**: a visitor could then send those headers themselves and
  sidestep the rate limits.
- Have the proxy *set* `X-Forwarded-For` to the client address rather than
  append to what the client sent, for the same reason.
- The chat WebSocket refuses any connection whose `Origin` does not match the
  `Host` header, which stops other websites opening it with a visitor's cookie.
  Most proxies pass `Host` through unchanged and nothing more is needed. If
  yours rewrites it, chat will fail to connect; list the public origin in
  `SISYPHUS_ALLOWED_ORIGINS=https://bbs.example.org` (comma-separated for several).
- The proxy must pass WebSocket upgrades for `/ws/chat`.
- The board sets its own security headers (CSP, HSTS, frame and referrer
  policy); the proxy should not add them again.

## Who can do what

| Level | Who | Can |
|---|---|---|
| 0 | Everyone who registers | Read and post on boards, like posts, chat, DM, play games. |
| 1 | Admins | Also: create boards and chat channels, delete posts, threads, files and chat messages, broadcast announcements, delete regular users, grant file access, make invitations, post links, and use the game's sysop tools. |
| 2 | The superadmin (the first account, or the one `create_superadmin.py` made) | Also: promote and demote admins. Cannot be demoted or deleted through the site. |

**Regular users cannot post links** on boards, in chat, or in profiles; admins
can. Nobody can on the game's tavern wall.

**The file area is earned.** A regular user sees it once all four are true: an
admin has approved them (Admin page), they have logged in on five consecutive
days, someone has liked one of their posts, and they have played a game (a
finished Mille Bornes game, or gaining a level in *The Long Climb*). Admins
always have access. Uploads are limited to 10 MB and to a list of document,
image, archive, audio and video types.

New passwords need at least 8 characters (at most 72 bytes).

### Invitations

With `SISYPHUS_INVITE_ONLY=1` in `.env` (the deploy script's default), the New
User tab asks for an invitation code and refuses to register without one. Admins
make codes on the Admin page: one button, an optional note of who it is for, and
the page shows the link to hand over (`https://your.host/?invite=CODE`). A code
admits one person and expires after seven days; open ones can be revoked. Who
invited whom is recorded on the account and shown on their profile. Turn the
setting off and registration is open again; a code still works and still
records the introduction.

On an empty database nobody can make a code, so create the superadmin from
the command line first, or let the deploy script do it.

## Resetting everything

This deletes the database **and every uploaded file**. The next account to
register becomes superadmin, or make one with `create_superadmin.py`.

Locally:

```sh
./sisyphus.sh stop
.venv/bin/python admin/reset_db.py      # asks first; --yes to skip the question
./sisyphus.sh start
```

On a server:

```sh
sudo systemctl stop sisyphus
sudo -u sisyphus /opt/sisyphus/.venv/bin/python /opt/sisyphus/admin/reset_db.py
sudo -u sisyphus /opt/sisyphus/.venv/bin/python /opt/sisyphus/admin/create_superadmin.py yourname
sudo systemctl start sisyphus
```

**Stop the server first.** A running server keeps the old database open, so
deleting the file underneath it changes nothing it can see: every account, the
admin included, carries on working until the next restart. The script refuses to
run while something is listening on the BBS port for exactly this reason
(`--force` overrides).

## Backups

Everything that matters is two things: the database (`db/sisyphus.db`, plus its
`-wal` and `-shm` companions while the server runs) and `file_store/`. Also keep
a copy of `.env` somewhere safe and private.

**On a server** the deploy script installs a nightly job that writes a
consistent copy of the database, an archive of the uploads, and `.env` to
`/var/backups/sisyphus`, keeping 14 days. It does not copy them anywhere else;
arrange that yourself (rsync, rclone, whatever you trust), because a backup on
the machine that failed is not a backup.

**Locally**, the simplest correct backup is to stop the server and copy both.
While it is running, use SQLite's own tool so you get a consistent copy:

```sh
mkdir -p backup
sqlite3 db/sisyphus.db ".backup 'backup/sisyphus-$(date +%F).db'"
```

**To restore**, stop the server, put the database file back in place of
`db/sisyphus.db` (remove any `-wal` and `-shm` files beside it), put the uploads
back in `file_store/`, and start it. On a server the paths are under
`/opt/sisyphus` and the files must be owned by the `sisyphus` user.

## Limits worth knowing

| What | Limit |
|---|---|
| Failed logins | 5 per address per 5 minutes; on a server, fail2ban then bans the address at the firewall after 10 in 10 minutes |
| Registrations | 10 per address per hour |
| Board posts and threads | 30 per user per 5 minutes (admins exempt) |
| Chat messages | 20 per user per 10 seconds |
| Uploads | 20 per user per hour, 10 MB each |
| Any other request body | 1 MB |

Rate limits are kept in memory, per process, and reset on restart.

## Games

- **Mille Bornes** (`/games/mille`) — the card game, against the computer or
  another user. Games are held in memory.
- **The Long Climb** (`/games/climb`) — an original daily-turn adventure in the
  tradition of early-'90s BBS door games. Fifteen climbs a day up a mountain
  with a dragon on top; about a month to the summit, and then you start again.
  Characters live in the database. The game day turns over at midnight in
  `SISYPHUS_TZ`. Design and rules:
  [`docs/long-climb/DESIGN.md`](docs/long-climb/DESIGN.md).

Sysop tools in The Long Climb (admins only): remove a line from the tavern wall
(a button beside the line), and reset a climber (a button on the Stele).

To see what a change to the game's numbers does to the length of a climb, edit
`lib/climb/data.py` and run:

```sh
.venv/bin/python -m lib.climb.sim
```

The price of healing, in particular, is far more sensitive than it looks. Read
the comment on it before touching it.

## The opening screen

The picture on the login page is a 1987 Sierra-style scene: sixteen EGA
colours, double-wide pixels, the PC 8x8 font for the title, and Sisyphus with
his boulder. It is generated, not hand-edited, and written into the page as an
SVG of rectangles so it is crisp at any size:

```sh
.venv/bin/python admin/login_art.py            # a rough look at it as text
.venv/bin/python admin/login_art.py --write    # put it into the login page
```

Change the sprite or the scene in `admin/login_art.py`. A test fails if the
page and the generator disagree.

## Development

```sh
.venv/bin/python -m pytest -q        # the whole suite, about two minutes
.venv/bin/python -m pytest -q -k climb
```

Tests use a temporary database and a temporary file store; they never touch
your real data. Three conventions are enforced by tests rather than by memory:

- **No inline script or style anywhere.** The Content-Security-Policy is
  `script-src 'self'; style-src 'self'`, so an `onclick=`, a `style=`, or an
  inline `<script>` would silently stop working in the browser. Scripts go in
  `frontend/static/js/`, styles are classes in `style.css`, and page data
  reaches scripts through `data-*` attributes. `tests/test_csp.py` fails on any
  violation.
- **The two dependency lists name the same packages**, and every third-party
  import is declared (`tests/test_packaging.py`).
- **The game's prose is all in `lib/climb/text.py`**, and a test fails on any
  line there that nothing says, or any creature without its lines.

The deploy script is not covered by the test suite. Before changing it, know
that it has been run end to end in a Debian 13 container with systemd; do the
same after.

```
src/app.py               entry point: logging, database, TLS, uvicorn
lib/web_server.py        the FastAPI app, middleware, routers
lib/routes/              one module per area: auth, boards, chat, files, admin, games, climb
lib/climb/               The Long Climb: data, rules, scenes, text, store, sim
lib/                     auth, boards, chat, files, invites, csrf, ratelimit, bodylimit, db, config, ...
frontend/templates/      Jinja pages        frontend/static/   CSS and JS
admin/                   reset_db.py, create_superadmin.py, login_art.py
deploy/                  install-debian.sh: the server installer and updater
docs/                    design documents
tests/
```

## Design documents

- [`docs/long-climb/DESIGN.md`](docs/long-climb/DESIGN.md) — The Long Climb, as built.
- [`docs/federation/`](docs/federation/) — a specification (parked, not built)
  for linking independently hosted boards through a relay that cannot read what
  it carries: threat model and wire protocol.
