# power-monitor

Sends a phone alert when the power goes out at home.

A Raspberry Pi and the router sit on a UPS. A TP-Link Kasa smart plug sits on
normal power. Every 30 seconds the Pi checks the plug. If the plug stops
answering but the internet is still up, the power is out, and an alert goes
out through [ntfy.sh](https://ntfy.sh). When the plug comes back, a "power
restored" alert follows.

If the plug and the internet are both down, it's treated as a network problem
and no alert is sent. This means the **modem must also be on the UPS**,
otherwise an outage takes the internet down with it and no alert ever fires.

## Setup (Raspberry Pi OS)

```bash
sudo apt install -y git tzdata-legacy
git clone https://github.com/computerguycj/power-monitor.git ~/power-monitor
cd ~/power-monitor
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Find the plug's IP:

```bash
venv/bin/kasa discover
```

`tzdata-legacy` is needed because Kasa plugs can report old-style time zone
names like `MST7MDT`, which Debian Trixie no longer installs by default.
Without it, every check fails and you get false outage alerts.

Give the plug a DHCP reservation in your router so the IP doesn't change.

Configure:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Pick a long random `NTFY_TOPIC`, for example from `openssl rand -hex 16`, and
subscribe to it in the ntfy phone app.

Test run:

```bash
set -a; . ./.env; set +a
venv/bin/python power_monitor.py
```

Unplug the Kasa plug for a minute to see an alert, then plug it back in.

Install as a service:

```bash
sudo cp power-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now power-monitor
journalctl -u power-monitor -f
```

The unit file assumes user `chris` and `/home/chris/power-monitor`. Edit it if
yours differ.

## Email alerts

ntfy.sh no longer sends email for anonymous users. To get email too:
create an ntfy.sh account, verify your address under Account, create an
access token, and set both `NTFY_EMAIL` and `NTFY_TOKEN`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PLUG_HOST` | required | Kasa plug IP |
| `NTFY_TOPIC` | required | ntfy topic, treat it like a password |
| `NTFY_EMAIL` | none | Also relay alerts to this address (needs `NTFY_TOKEN`) |
| `NTFY_TOKEN` | none | ntfy account access token; required for email on ntfy.sh |
| `NTFY_SERVER` | `https://ntfy.sh` | Self-hosted ntfy server |
| `PING_HOST` | `1.1.1.1` | Host used to check the internet |
| `POLL_SECONDS` | `30` | Time between checks |
| `FAIL_THRESHOLD` | `2` | Missed checks in a row before alerting |

## License

GPL-3.0-or-later, matching [python-kasa](https://github.com/python-kasa/python-kasa).
See `LICENSE`.
