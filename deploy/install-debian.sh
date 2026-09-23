#!/bin/bash
#
# Sisyphus BBS on Debian 13: install, or update, a live server.
#
#   sudo ./install-debian.sh --domain bbs.example.org --email you@example.org
#
# What it sets up, all of it re-runnable (a second run pulls the latest code,
# reinstalls dependencies and restarts; it never touches .env, the database,
# uploads, or a certificate that is still good):
#
#   * a system user `sisyphus` and the code in /opt/sisyphus, from GitHub
#   * a virtualenv with the pinned requirements
#   * .env with a fresh SISYPHUS_SECRET, bound to 127.0.0.1 behind the proxy,
#     and registration closed (invite-only) unless told otherwise
#   * the superadmin account, made before the site is reachable, so nobody
#     can register first and take it
#   * a locked-down systemd service (read-only filesystem except db/, file_store/, log/)
#   * nginx on 443 (TLS 1.2/1.3, modern ciphers only, HTTP/2, WebSocket for chat),
#     and on 80 for the ACME challenge plus a redirect to https
#   * a Let's Encrypt certificate via certbot, renewed from cron twice a day,
#     with nginx reloaded whenever a new one lands
#   * ufw: deny everything inbound except SSH, 80 and 443
#   * fail2ban: the stock sshd jail, plus a jail that bans an address after
#     repeated failed logins to the BBS (seen in the nginx access log)
#   * log rotation, a nightly local backup, unattended security upgrades,
#     and a `sisyphus-update` command for later
#
# Options:
#   --domain NAME      public hostname (required); DNS must already point here
#   --email ADDR       Let's Encrypt account address, gets expiry warnings
#                      (required unless --self-signed)
#   --admin USER       create the superadmin account with this username; the
#                      password is asked for on the terminal (or read from the
#                      SISYPHUS_ADMIN_PASSWORD environment variable if set)
#   --open             leave registration open instead of invite-only
#   --name "Text"      the board's name in the header (default: Sisyphus BBS)
#   --tz ZONE          IANA zone that turns the game day over (default: server's)
#   --repo URL         git repository (default: the GitHub repo)
#   --branch NAME      branch to deploy (default: main)
#   --deploy-key FILE  private key of a read-only GitHub deploy key; it is
#                      installed for the sisyphus user and the clone uses SSH.
#                      Needed while the repository is private. Make one with
#                        ssh-keygen -t ed25519 -N '' -f sisyphus-deploy
#                      and add sisyphus-deploy.pub under the repository's
#                      Settings > Deploy keys (read-only).
#   --staging          use Let's Encrypt's staging CA (untrusted cert, no rate limits)
#   --self-signed      no Let's Encrypt: a self-signed certificate instead, for a
#                      box without public DNS yet; re-run without it later
#   --no-firewall      leave ufw alone
#   --skip-dns-check   do not insist that --domain resolves before asking for a cert

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

DOMAIN=""
EMAIL=""
BBS_NAME="Sisyphus BBS"
ADMIN_USER=""
INVITE_ONLY=1
TZ_NAME=""
REPO="https://github.com/tedfiedler/sisyphus-bbs.git"
BRANCH="main"
DEPLOY_KEY=""
STAGING=""
SELF_SIGNED=0
FIREWALL=1
DNS_CHECK=1

while [ $# -gt 0 ]; do
    case "$1" in
        --domain) DOMAIN="$2"; shift 2 ;;
        --email) EMAIL="$2"; shift 2 ;;
        --name) BBS_NAME="$2"; shift 2 ;;
        --admin) ADMIN_USER="$2"; shift 2 ;;
        --open) INVITE_ONLY=0; shift ;;
        --tz) TZ_NAME="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --deploy-key) DEPLOY_KEY="$2"; shift 2 ;;
        --staging) STAGING="--staging"; shift ;;
        --self-signed) SELF_SIGNED=1; shift ;;
        --no-firewall) FIREWALL=0; shift ;;
        --skip-dns-check) DNS_CHECK=0; shift ;;
        -h|--help) awk 'NR > 1 && /^set -euo/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

[ -n "$DOMAIN" ] || { echo "--domain is required" >&2; exit 2; }
[ -n "$EMAIL" ] || [ "$SELF_SIGNED" -eq 1 ] || { echo "--email is required" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)." >&2; exit 2; }
if [ -n "$DEPLOY_KEY" ]; then
    [ -r "$DEPLOY_KEY" ] || { echo "--deploy-key: cannot read $DEPLOY_KEY" >&2; exit 2; }
    # A deploy key only works over SSH; turn the https form of a GitHub URL around.
    case "$REPO" in
        https://github.com/*) REPO="git@github.com:${REPO#https://github.com/}" ;;
    esac
fi

if [ -r /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" != "debian" ]; then
        echo "This script is written for Debian; found ${PRETTY_NAME:-something else}." >&2
        exit 2
    fi
    if [ "${VERSION_ID:-}" != "13" ]; then
        echo "Warning: written for Debian 13, this is ${PRETTY_NAME:-unknown}. Carrying on." >&2
    fi
fi

APP_USER="sisyphus"
APP_HOME="/var/lib/sisyphus"
APP_DIR="/opt/sisyphus"
ACME_ROOT="/var/www/letsencrypt"
BACKUP_DIR="/var/backups/sisyphus"
PORT=8000

say() { printf '\n==> %s\n' "$*"; }
as_app() { runuser -u "$APP_USER" -- env HOME="$APP_HOME" "$@"; }

# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

say "Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
    nginx certbot git openssh-client python3 python3-venv sqlite3 ca-certificates curl \
    ufw fail2ban unattended-upgrades

# ---------------------------------------------------------------------------
# User and code
# ---------------------------------------------------------------------------

say "Creating the $APP_USER user"
if ! id "$APP_USER" >/dev/null 2>&1; then
    adduser --system --group --home "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$APP_DIR"

if [ -n "$DEPLOY_KEY" ]; then
    say "Installing the deploy key for $APP_USER"
    install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$APP_HOME/.ssh"
    install -o "$APP_USER" -g "$APP_USER" -m 600 "$DEPLOY_KEY" "$APP_HOME/.ssh/deploy_key"
    # Pin GitHub's host key now, so the clone never has to ask and cannot be
    # talked to by an impostor. Fetched over DNS-verified TLS from GitHub's API.
    curl -fsS https://api.github.com/meta \
        | python3 -c "import json,sys; [print('github.com', k) for k in json.load(sys.stdin)['ssh_keys']]" \
        > "$APP_HOME/.ssh/known_hosts"
    cat > "$APP_HOME/.ssh/config" <<EOF
Host github.com
    IdentityFile $APP_HOME/.ssh/deploy_key
    IdentitiesOnly yes
    StrictHostKeyChecking yes
EOF
    chown -R "$APP_USER:$APP_USER" "$APP_HOME/.ssh"
    chmod 600 "$APP_HOME/.ssh/config" "$APP_HOME/.ssh/known_hosts"
fi

say "Fetching the code ($BRANCH from $REPO)"
if [ -d "$APP_DIR/.git" ]; then
    as_app git -C "$APP_DIR" fetch --quiet origin
    as_app git -C "$APP_DIR" checkout --quiet "$BRANCH"
    as_app git -C "$APP_DIR" pull --quiet --ff-only origin "$BRANCH"
else
    if [ -n "$(ls -A "$APP_DIR")" ]; then
        echo "$APP_DIR exists and is not a git checkout; move it aside first." >&2
        exit 1
    fi
    as_app git clone --quiet --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

say "Installing Python dependencies"
[ -x "$APP_DIR/.venv/bin/python" ] || as_app python3 -m venv "$APP_DIR/.venv"
as_app "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
as_app "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

for d in db file_store log; do
    install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$APP_DIR/$d"
done

# ---------------------------------------------------------------------------
# .env: written once, never overwritten
# ---------------------------------------------------------------------------

if [ -f "$APP_DIR/.env" ]; then
    say "Keeping the existing .env"
else
    say "Writing .env with a new secret"
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
    {
        echo "SISYPHUS_SECRET=$SECRET"
        echo "SISYPHUS_NAME=$BBS_NAME"
        echo "SISYPHUS_WEB_HOST=127.0.0.1"
        echo "SISYPHUS_WEB_PORT=$PORT"
        echo "SISYPHUS_TRUST_PROXY=1"
        echo "SISYPHUS_INVITE_ONLY=$INVITE_ONLY"
        [ -n "$TZ_NAME" ] && echo "SISYPHUS_TZ=$TZ_NAME"
    } > "$APP_DIR/.env"
    unset SECRET
fi
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

# ---------------------------------------------------------------------------
# The superadmin, before anything is listening
# ---------------------------------------------------------------------------

if [ -n "$ADMIN_USER" ]; then
    say "Creating the superadmin account '$ADMIN_USER'"
    cd "$APP_DIR"
    if [ -n "${SISYPHUS_ADMIN_PASSWORD:-}" ]; then
        printf '%s\n' "$SISYPHUS_ADMIN_PASSWORD" \
            | as_app .venv/bin/python admin/create_superadmin.py "$ADMIN_USER" --if-empty --password-stdin
    elif [ -t 0 ]; then
        as_app .venv/bin/python admin/create_superadmin.py "$ADMIN_USER" --if-empty
    else
        echo "No terminal to ask for a password on. Create the account afterwards with:" >&2
        echo "    cd $APP_DIR && sudo -u $APP_USER .venv/bin/python admin/create_superadmin.py $ADMIN_USER" >&2
    fi
    cd - >/dev/null
fi

# ---------------------------------------------------------------------------
# systemd service
# ---------------------------------------------------------------------------

say "Installing the systemd service"
cat > /etc/systemd/system/sisyphus.service <<EOF
[Unit]
Description=Sisyphus BBS
Documentation=https://github.com/tedfiedler/sisyphus-bbs
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$APP_DIR/.venv/bin/python src/app.py
Restart=always
RestartSec=3

# The process may write only where the application keeps its data.
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$APP_DIR/db $APP_DIR/file_store $APP_DIR/log
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
ProtectProc=invisible
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
SystemCallArchitectures=native
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @resources
CapabilityBoundingSet=
UMask=0077

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --quiet sisyphus
systemctl restart sisyphus

# ---------------------------------------------------------------------------
# nginx, stage one: plain HTTP for the ACME challenge
# ---------------------------------------------------------------------------

say "Configuring nginx"
install -d -o www-data -g www-data -m 755 "$ACME_ROOT"
rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/conf.d/sisyphus-hardening.conf <<'EOF'
# Applies to every server block on this host. (Debian's nginx.conf already
# turns server_tokens off and limits TLS to 1.2 and 1.3.)
client_body_timeout 15s;
client_header_timeout 15s;
send_timeout 30s;
keepalive_timeout 65s;
limit_conn_zone $binary_remote_addr zone=sisyphus_conn:10m;
EOF

write_http_server() {
    cat <<EOF
# Port 80 does two things only: answer the ACME challenge and send everyone
# else to https. The redirect names the site, not the Host header a client sent.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location ^~ /.well-known/acme-challenge/ {
        root $ACME_ROOT;
        default_type text/plain;
    }

    location / {
        return 301 https://$DOMAIN\$request_uri;
    }
}
EOF
}

SITE=/etc/nginx/sites-available/sisyphus
write_http_server > "$SITE"
ln -sf "$SITE" /etc/nginx/sites-enabled/sisyphus
nginx -t
systemctl enable --quiet nginx
if systemctl is-active --quiet nginx; then systemctl reload nginx; else systemctl start nginx; fi

# ---------------------------------------------------------------------------
# Let's Encrypt
# ---------------------------------------------------------------------------

if [ "$SELF_SIGNED" -eq 1 ]; then
    say "Making a self-signed certificate (no Let's Encrypt)"
    CERT_DIR=/etc/ssl/sisyphus
    install -d -m 700 "$CERT_DIR"
    if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
        openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
            -days 825 -subj "/CN=$DOMAIN" -addext "subjectAltName=DNS:$DOMAIN" \
            -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" 2>/dev/null
    fi
    rm -f /etc/cron.d/sisyphus-certbot
else
    if [ "$DNS_CHECK" -eq 1 ] && ! getent ahosts "$DOMAIN" >/dev/null; then
        echo "$DOMAIN does not resolve. Point its A (and AAAA) record at this server," >&2
        echo "wait for DNS, and run this again. (--skip-dns-check to override.)" >&2
        exit 1
    fi

    say "Requesting the certificate for $DOMAIN"
    # shellcheck disable=SC2086
    certbot certonly --webroot -w "$ACME_ROOT" -d "$DOMAIN" \
        --email "$EMAIL" --agree-tos --no-eff-email --non-interactive \
        --keep-until-expiring $STAGING

    CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

    # nginx picks up a renewed certificate only when reloaded.
    install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
    printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
    chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx

    # Renew from cron, as asked. Debian's certbot package also ships a systemd
    # timer for the same job; it is switched off so only one scheduler runs.
    # `certbot renew` does nothing until a certificate is within 30 days of
    # expiry, and when run from cron it waits a random few minutes first so
    # every server in the world does not hit Let's Encrypt at the same second.
    systemctl disable --quiet --now certbot.timer 2>/dev/null || true
    cat > /etc/cron.d/sisyphus-certbot <<'EOF'
# Let's Encrypt renewal for Sisyphus BBS, twice a day.
MAILTO=root
23 3,15 * * * root /usr/bin/certbot -q renew
EOF
    chmod 644 /etc/cron.d/sisyphus-certbot
fi

# ---------------------------------------------------------------------------
# nginx, stage two: the real site
# ---------------------------------------------------------------------------

say "Enabling HTTPS"
{
    write_http_server
    cat <<EOF

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $DOMAIN;

    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;

    # TLS 1.2 with forward-secret AEAD suites only, and TLS 1.3. No RSA key
    # exchange, no CBC, so no DH parameters are needed either. Let's Encrypt
    # no longer runs OCSP responders, so stapling is deliberately absent.
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:sisyphus_ssl:10m;
    ssl_session_tickets off;

    # The application sets its own security headers (CSP, HSTS, frame and
    # referrer policy, no-store) on every response, so nothing is added here
    # that would arrive twice.

    # Uploads are capped at 10 MB by the application; this is just above that
    # so anything larger is refused here with a clean 413.
    client_max_body_size 11m;
    limit_conn sisyphus_conn 40;

    access_log /var/log/nginx/sisyphus.access.log;
    error_log /var/log/nginx/sisyphus.error.log;

    # Browsers ask for this on every page; the application has none.
    location = /favicon.ico {
        access_log off;
        return 204;
    }

    location ~ /\\. {
        deny all;
    }

    # Chat. The application pings the socket itself, so an idle one is
    # closed by the application rather than by this timeout.
    location = /ws/chat {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        # Host is passed through unchanged: the application compares the chat
        # socket's Origin against it. X-Forwarded-For is set, not appended,
        # so a client cannot smuggle a fake address in for the rate limiter.
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }
}
EOF
} > "$SITE"
nginx -t
systemctl reload nginx

# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------

if [ "$FIREWALL" -eq 1 ]; then
    say "Configuring the firewall (ufw)"
    # Never lock ourselves out: allow whatever port(s) sshd actually listens on.
    SSH_PORTS=$(sshd -T 2>/dev/null | awk '/^port /{print $2}' | sort -u)
    [ -n "$SSH_PORTS" ] || SSH_PORTS=22
    for p in $SSH_PORTS; do
        ufw allow "$p/tcp" comment "ssh" >/dev/null
    done
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    ufw allow 80/tcp comment "acme challenge and redirect to https" >/dev/null
    ufw allow 443/tcp comment "sisyphus bbs" >/dev/null
    ufw --force enable >/dev/null
    ufw status | sed 's/^/    /'
fi

# ---------------------------------------------------------------------------
# fail2ban
# ---------------------------------------------------------------------------

say "Configuring fail2ban"
# The application already limits logins to 5 failures per address per five
# minutes and answers 429 after that. This jail is for whoever keeps going:
# ten failed or throttled login attempts within ten minutes bans the address
# at the firewall for an hour, doubling on each repeat.
cat > /etc/fail2ban/filter.d/sisyphus-login.conf <<'EOF'
# Failed (401) or throttled (429) logins to Sisyphus BBS, from nginx's access log.
[Definition]
failregex = ^<HOST> - \S+ \[\] "POST /login HTTP/[0-9.]+" (?:401|429) 
ignoreregex =
EOF
cat > /etc/fail2ban/jail.d/sisyphus.local <<'EOF'
[sshd]
enabled = true

[sisyphus-login]
enabled = true
filter = sisyphus-login
logpath = /var/log/nginx/sisyphus.access.log
port = http,https
maxretry = 10
findtime = 10m
bantime = 1h
bantime.increment = true
bantime.maxtime = 1d
EOF
touch /var/log/nginx/sisyphus.access.log
systemctl enable --quiet fail2ban
systemctl restart fail2ban

# ---------------------------------------------------------------------------
# Housekeeping: log rotation, backups, security updates, an update command
# ---------------------------------------------------------------------------

say "Installing log rotation, nightly backups, unattended upgrades"

# The application keeps its log file open, so it is copied and truncated in
# place rather than moved.
cat > /etc/logrotate.d/sisyphus <<EOF
$APP_DIR/log/sisyphus.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF

install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$BACKUP_DIR"
cat > /usr/local/bin/sisyphus-backup <<EOF
#!/bin/sh
# Consistent copy of the live database, the uploads, and .env. Keeps 14 days.
# Copy $BACKUP_DIR somewhere off this machine; that part is up to you.
set -eu
stamp=\$(date +%F)
sqlite3 "$APP_DIR/db/sisyphus.db" ".backup '$BACKUP_DIR/sisyphus-\$stamp.db'"
tar -czf "$BACKUP_DIR/file_store-\$stamp.tar.gz" -C "$APP_DIR" file_store
cp -p "$APP_DIR/.env" "$BACKUP_DIR/env-\$stamp"
find "$BACKUP_DIR" -type f -mtime +14 -delete
EOF
chmod 755 /usr/local/bin/sisyphus-backup
cat > /etc/cron.d/sisyphus-backup <<EOF
MAILTO=root
10 4 * * * root runuser -u $APP_USER -- /usr/local/bin/sisyphus-backup
EOF
chmod 644 /etc/cron.d/sisyphus-backup

cat > /usr/local/bin/sisyphus-update <<EOF
#!/bin/sh
# Pull the latest code, install dependencies, restart. Mille Bornes games in
# progress are lost on restart; everything else is in the database.
set -eu
runuser -u $APP_USER -- env HOME=$APP_HOME git -C "$APP_DIR" pull --ff-only
runuser -u $APP_USER -- env HOME=$APP_HOME "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
systemctl restart sisyphus
systemctl --no-pager --lines=5 status sisyphus
EOF
chmod 755 /usr/local/bin/sisyphus-update

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# ---------------------------------------------------------------------------
# Check and report
# ---------------------------------------------------------------------------

say "Checking"
sleep 2
if ! systemctl is-active --quiet sisyphus; then
    echo "The sisyphus service is not running:" >&2
    journalctl -u sisyphus --no-pager --lines=30 >&2
    exit 1
fi
if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/"; then
    echo "    application answers on 127.0.0.1:$PORT"
else
    echo "    application did not answer on 127.0.0.1:$PORT; see: journalctl -u sisyphus" >&2
fi
if curl -fsS -o /dev/null --resolve "$DOMAIN:443:127.0.0.1" -k "https://$DOMAIN/"; then
    echo "    nginx serves https://$DOMAIN"
else
    echo "    nginx did not serve https://$DOMAIN; see: /var/log/nginx/sisyphus.error.log" >&2
fi

cat <<EOF

Done.
EOF
if [ -n "$ADMIN_USER" ]; then
    echo "Log in at https://$DOMAIN as $ADMIN_USER. Invitations are made on the Admin page."
else
    echo "Now open https://$DOMAIN and register: THE FIRST ACCOUNT BECOMES THE"
    echo "SUPERADMIN, so do it before telling anyone the address. (Next time, pass"
    echo "--admin USER and the account is made before the site is reachable.)"
fi
cat <<EOF

    service     systemctl status sisyphus        journalctl -u sisyphus -f
    restart     systemctl restart sisyphus
    update      sisyphus-update                  (or run this script again)
    settings    $APP_DIR/.env                    (restart after editing)
    app log     $APP_DIR/log/sisyphus.log
    nginx log   /var/log/nginx/sisyphus.*.log
    backups     $BACKUP_DIR (nightly at 04:10, 14 days kept; copy them off-box)
    bans        fail2ban-client status sisyphus-login
    cert        certbot certificates             renewed by /etc/cron.d/sisyphus-certbot
EOF
if [ "$SELF_SIGNED" -eq 1 ]; then
    echo "    The certificate is SELF-SIGNED; browsers will warn. Once $DOMAIN has public"
    echo "    DNS, run this script again with --email and without --self-signed."
fi
