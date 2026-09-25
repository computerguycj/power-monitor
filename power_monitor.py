#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Power outage monitor.

Polls a Kasa smart plug that sits on normal (non-UPS) power. If the plug stops
answering while the internet is still up, the power is out. Alerts go out via
ntfy.sh.
"""

import asyncio
import logging
import os
import sys
import time

import requests
from kasa import Discover

log = logging.getLogger("power-monitor")


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


PLUG_HOST = env("PLUG_HOST", required=True)
NTFY_TOPIC = env("NTFY_TOPIC", required=True)
NTFY_SERVER = env("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_EMAIL = env("NTFY_EMAIL", "")
PING_HOST = env("PING_HOST", "1.1.1.1")
POLL_SECONDS = int(env("POLL_SECONDS", "30"))
FAIL_THRESHOLD = int(env("FAIL_THRESHOLD", "2"))


def send_alert(title, message, priority="urgent", tags=""):
    headers = {"Title": title, "Priority": priority}
    if tags:
        headers["Tags"] = tags
    if NTFY_EMAIL:
        headers["X-Email"] = NTFY_EMAIL
    try:
        resp = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Alert sent: %s", title)
        return True
    except requests.RequestException as exc:
        log.error("Alert failed: %s", exc)
        return False


async def internet_up():
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", "3", PING_HOST,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await proc.wait() == 0


class PlugChecker:
    def __init__(self, host):
        self.host = host
        self.dev = None

    async def reachable(self):
        try:
            if self.dev is None:
                self.dev = await Discover.discover_single(self.host)
            await self.dev.update()
            return True
        except Exception as exc:  # timeouts, connection errors, KasaException
            log.debug("Plug check failed: %s", exc)
            await self.reset()
            return False

    async def reset(self):
        if self.dev is not None:
            try:
                await self.dev.disconnect()
            except Exception:
                pass
        self.dev = None


def fmt_duration(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log.info("Watching plug at %s every %ss", PLUG_HOST, POLL_SECONDS)

    plug = PlugChecker(PLUG_HOST)
    failures = 0
    outage_started = None  # set only once an outage alert has gone out

    while True:
        if await plug.reachable():
            if outage_started is not None:
                duration = fmt_duration(time.time() - outage_started)
                await asyncio.to_thread(
                    send_alert,
                    "Power restored",
                    f"Garage plug is back. Outage lasted about {duration}.",
                    "high",
                    "white_check_mark",
                )
                outage_started = None
            failures = 0
        else:
            failures += 1
            log.warning("Plug unreachable (%d in a row)", failures)
            if outage_started is None and failures >= FAIL_THRESHOLD:
                if await internet_up():
                    outage_started = time.time()
                    await asyncio.to_thread(
                        send_alert,
                        "Power outage",
                        "Garage plug stopped answering and the internet is up. "
                        "Power is probably out.",
                        "urgent",
                        "warning",
                    )
                else:
                    log.warning("Internet also down, treating as a network problem")

        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
