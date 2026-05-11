import sys
import os
import types
import io as _io
import ssl
import certifi

try:
    import imghdr
except ModuleNotFoundError:
    try:
        from PIL import Image as _PILImage
    except Exception as _pil_err:
        raise RuntimeError("Pillow required") from _pil_err

    def _imghdr_what(file, h=None):
        try:
            if h is not None:
                data = h
            elif isinstance(file, (str, bytes, bytearray)):
                with open(file, "rb") as _f:
                    data = _f.read(64)
            elif hasattr(file, "read"):
                _pos = None
                try:
                    _pos = file.tell()
                except Exception:
                    pass
                data = file.read(64)
                if _pos is not None:
                    try:
                        file.seek(_pos)
                    except Exception:
                        pass
            else:
                return None
            if not isinstance(data, (bytes, bytearray)):
                return None
            img = _PILImage.open(_io.BytesIO(data))
            fmt = (img.format or "").lower()
            return {
                "jpeg": "jpeg", "png": "png", "gif": "gif",
                "bmp": "bmp", "webp": "webp", "tiff": "tiff",
            }.get(fmt)
        except Exception:
            return None

    _imghdr_mod = types.ModuleType("imghdr")
    _imghdr_mod.what = _imghdr_what
    sys.modules["imghdr"] = _imghdr_mod
    imghdr = _imghdr_mod

import logging
import sqlite3
import time
import re
import threading
import hashlib
import asyncio
import json
import aiohttp
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
import openpyxl
from aiohttp import web

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN           = "8313925262:AAFBgY13zTdARtEuWuIdFp8-rKac6DopNjU"
BOT_NAME            = "ᴍʀ.ᴀғʀɪx"
BOT_USERNAME        = "mrafrix_bot"
BOT_LINK            = "https://t.me/mrafrix_bot"
BASE_ADMIN_IDS      = [8339856952]

PANEL_BASE          = "https://imssms.org"
PANEL_LOGIN_PAGE    = f"{PANEL_BASE}/login"
PANEL_SIGNIN_URL    = f"{PANEL_BASE}/signin"
PANEL_CDR_URL       = f"{PANEL_BASE}/client/SMSCDRStats"
PANEL_DASHBOARD_URL = f"{PANEL_BASE}/client/SMSDashboard"
PANEL_USERNAME      = "Techbangla"
PANEL_PASSWORD      = "Techbangla"

MAIN_CHANNEL        = "@sage_xd"
MAIN_CHANNEL_LINK   = "https://t.me/sage_xd"
BACKUP_CHANNEL      = "@mr_afrix"
BACKUP_CHANNEL_LINK = "https://t.me/mr_afrix"
OTP_GROUP_LINK      = "https://t.me/afrixotpgc"
OTP_GROUP_ID        = -1003053441379
FORCE_CHANNELS      = ["@sage_xd", "@mr_afrix"]

BANNER_URL          = "https://files.catbox.moe/apvmgp.jpg"

DB_FILE             = "bot.db"
PORT                = int(os.environ.get("PORT", 8080))
POLL_INTERVAL       = 8
KEEPALIVE_INTERVAL  = 90
FLOOD_LIMIT         = 5
FLOOD_WINDOW        = 10
NUMBER_COOLDOWN     = 30

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

USER_STATE      = {}
flood_data      = {}
otp_cache       = set()
maintenance     = False
ADMIN_IDS       = list(BASE_ADMIN_IDS)

worker_info = {
    "running":    False,
    "logged_in":  False,
    "last_otp":   "—",
    "otps_today": 0,
    "last_login": "—",
    "errors":     0,
    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

COUNTRY_CODES = {
    "1": ("USA/Canada", "🇺🇸"), "7": ("Russia", "🇷🇺"), "20": ("Egypt", "🇪🇬"),
    "27": ("South Africa", "🇿🇦"), "30": ("Greece", "🇬🇷"), "31": ("Netherlands", "🇳🇱"),
    "32": ("Belgium", "🇧🇪"), "33": ("France", "🇫🇷"), "34": ("Spain", "🇪🇸"),
    "36": ("Hungary", "🇭🇺"), "39": ("Italy", "🇮🇹"), "40": ("Romania", "🇷🇴"),
    "41": ("Switzerland", "🇨🇭"), "43": ("Austria", "🇦🇹"), "44": ("United Kingdom", "🇬🇧"),
    "45": ("Denmark", "🇩🇰"), "46": ("Sweden", "🇸🇪"), "47": ("Norway", "🇳🇴"),
    "48": ("Poland", "🇵🇱"), "49": ("Germany", "🇩🇪"), "51": ("Peru", "🇵🇪"),
    "52": ("Mexico", "🇲🇽"), "53": ("Cuba", "🇨🇺"), "54": ("Argentina", "🇦🇷"),
    "55": ("Brazil", "🇧🇷"), "56": ("Chile", "🇨🇱"), "57": ("Colombia", "🇨🇴"),
    "58": ("Venezuela", "🇻🇪"), "60": ("Malaysia", "🇲🇾"), "61": ("Australia", "🇦🇺"),
    "62": ("Indonesia", "🇮🇩"), "63": ("Philippines", "🇵🇭"), "64": ("New Zealand", "🇳🇿"),
    "65": ("Singapore", "🇸🇬"), "66": ("Thailand", "🇹🇭"), "81": ("Japan", "🇯🇵"),
    "82": ("South Korea", "🇰🇷"), "84": ("Viet Nam", "🇻🇳"), "86": ("China", "🇨🇳"),
    "90": ("Turkey", "🇹🇷"), "91": ("India", "🇮🇳"), "92": ("Pakistan", "🇵🇰"),
    "93": ("Afghanistan", "🇦🇫"), "94": ("Sri Lanka", "🇱🇰"), "95": ("Myanmar", "🇲🇲"),
    "98": ("Iran", "🇮🇷"), "211": ("South Sudan", "🇸🇸"), "212": ("Morocco", "🇲🇦"),
    "213": ("Algeria", "🇩🇿"), "216": ("Tunisia", "🇹🇳"), "218": ("Libya", "🇱🇾"),
    "220": ("Gambia", "🇬🇲"), "221": ("Senegal", "🇸🇳"), "222": ("Mauritania", "🇲🇷"),
    "223": ("Mali", "🇲🇱"), "224": ("Guinea", "🇬🇳"), "225": ("Côte d'Ivoire", "🇨🇮"),
    "226": ("Burkina Faso", "🇧🇫"), "227": ("Niger", "🇳🇪"), "228": ("Togo", "🇹🇬"),
    "229": ("Benin", "🇧🇯"), "230": ("Mauritius", "🇲🇺"), "231": ("Liberia", "🇱🇷"),
    "232": ("Sierra Leone", "🇸🇱"), "233": ("Ghana", "🇬🇭"), "234": ("Nigeria", "🇳🇬"),
    "235": ("Chad", "🇹🇩"), "236": ("Central African Republic", "🇨🇫"),
    "237": ("Cameroon", "🇨🇲"), "238": ("Cape Verde", "🇨🇻"),
    "240": ("Equatorial Guinea", "🇬🇶"), "241": ("Gabon", "🇬🇦"), "242": ("Congo", "🇨🇬"),
    "243": ("DR Congo", "🇨🇩"), "244": ("Angola", "🇦🇴"), "245": ("Guinea-Bissau", "🇬🇼"),
    "248": ("Seychelles", "🇸🇨"), "249": ("Sudan", "🇸🇩"), "250": ("Rwanda", "🇷🇼"),
    "251": ("Ethiopia", "🇪🇹"), "252": ("Somalia", "🇸🇴"), "253": ("Djibouti", "🇩🇯"),
    "254": ("Kenya", "🇰🇪"), "255": ("Tanzania", "🇹🇿"), "256": ("Uganda", "🇺🇬"),
    "257": ("Burundi", "🇧🇮"), "258": ("Mozambique", "🇲🇿"), "260": ("Zambia", "🇿🇲"),
    "261": ("Madagascar", "🇲🇬"), "263": ("Zimbabwe", "🇿🇼"), "264": ("Namibia", "🇳🇦"),
    "265": ("Malawi", "🇲🇼"), "266": ("Lesotho", "🇱🇸"), "267": ("Botswana", "🇧🇼"),
    "268": ("Eswatini", "🇸🇿"), "269": ("Comoros", "🇰🇲"), "290": ("Saint Helena", "🇸🇭"),
    "291": ("Eritrea", "🇪🇷"), "297": ("Aruba", "🇦🇼"), "298": ("Faroe Islands", "🇫🇴"),
    "299": ("Greenland", "🇬🇱"), "350": ("Gibraltar", "🇬🇮"), "351": ("Portugal", "🇵🇹"),
    "352": ("Luxembourg", "🇱🇺"), "353": ("Ireland", "🇮🇪"), "354": ("Iceland", "🇮🇸"),
    "355": ("Albania", "🇦🇱"), "356": ("Malta", "🇲🇹"), "357": ("Cyprus", "🇨🇾"),
    "358": ("Finland", "🇫🇮"), "359": ("Bulgaria", "🇧🇬"), "370": ("Lithuania", "🇱🇹"),
    "371": ("Latvia", "🇱🇻"), "372": ("Estonia", "🇪🇪"), "373": ("Moldova", "🇲🇩"),
    "374": ("Armenia", "🇦🇲"), "375": ("Belarus", "🇧🇾"), "376": ("Andorra", "🇦🇩"),
    "377": ("Monaco", "🇲🇨"), "380": ("Ukraine", "🇺🇦"), "381": ("Serbia", "🇷🇸"),
    "382": ("Montenegro", "🇲🇪"), "385": ("Croatia", "🇭🇷"), "386": ("Slovenia", "🇸🇮"),
    "387": ("Bosnia and Herzegovina", "🇧🇦"), "389": ("North Macedonia", "🇲🇰"),
    "420": ("Czech Republic", "🇨🇿"), "421": ("Slovakia", "🇸🇰"), "423": ("Liechtenstein", "🇱🇮"),
    "500": ("Falkland Islands", "🇫🇰"), "501": ("Belize", "🇧🇿"), "502": ("Guatemala", "🇬🇹"),
    "503": ("El Salvador", "🇸🇻"), "504": ("Honduras", "🇭🇳"), "505": ("Nicaragua", "🇳🇮"),
    "506": ("Costa Rica", "🇨🇷"), "507": ("Panama", "🇵🇦"), "509": ("Haiti", "🇭🇹"),
    "591": ("Bolivia", "🇧🇴"), "592": ("Guyana", "🇬🇾"), "593": ("Ecuador", "🇪🇨"),
    "595": ("Paraguay", "🇵🇾"), "597": ("Suriname", "🇸🇷"), "598": ("Uruguay", "🇺🇾"),
    "670": ("East Timor", "🇹🇱"), "673": ("Brunei", "🇧🇳"), "675": ("Papua New Guinea", "🇵🇬"),
    "676": ("Tonga", "🇹🇴"), "677": ("Solomon Islands", "🇸🇧"), "678": ("Vanuatu", "🇻🇺"),
    "679": ("Fiji", "🇫🇯"), "685": ("Samoa", "🇼🇸"), "687": ("New Caledonia", "🇳🇨"),
    "689": ("French Polynesia", "🇵🇫"), "850": ("North Korea", "🇰🇵"),
    "852": ("Hong Kong", "🇭🇰"), "853": ("Macau", "🇲🇴"), "855": ("Cambodia", "🇰🇭"),
    "856": ("Laos", "🇱🇦"), "880": ("Bangladesh", "🇧🇩"), "886": ("Taiwan", "🇹🇼"),
    "960": ("Maldives", "🇲🇻"), "961": ("Lebanon", "🇱🇧"), "962": ("Jordan", "🇯🇴"),
    "963": ("Syria", "🇸🇾"), "964": ("Iraq", "🇮🇶"), "965": ("Kuwait", "🇰🇼"),
    "966": ("Saudi Arabia", "🇸🇦"), "967": ("Yemen", "🇾🇪"), "968": ("Oman", "🇴🇲"),
    "970": ("Palestine", "🇵🇸"), "971": ("UAE", "🇦🇪"), "972": ("Israel", "🇮🇱"),
    "973": ("Bahrain", "🇧🇭"), "974": ("Qatar", "🇶🇦"), "975": ("Bhutan", "🇧🇹"),
    "976": ("Mongolia", "🇲🇳"), "977": ("Nepal", "🇳🇵"), "992": ("Tajikistan", "🇹🇯"),
    "993": ("Turkmenistan", "🇹🇲"), "994": ("Azerbaijan", "🇦🇿"), "995": ("Georgia", "🇬🇪"),
    "996": ("Kyrgyzstan", "🇰🇬"), "998": ("Uzbekistan", "🇺🇿"),
}

DEFAULT_SERVICES = [
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Google",
    "TikTok", "Twitter/X", "Snapchat", "Discord", "Line",
    "WeChat", "Viber", "Signal", "Binance", "Bybit",
    "OKX", "Bitget", "Coinbase", "Kraken", "Other",
]


class Database:
    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def fetchone(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def init(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT    DEFAULT '',
                    first_name TEXT    DEFAULT '',
                    joined_at  TEXT    DEFAULT (datetime('now')),
                    is_banned  INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS otp_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash       TEXT    UNIQUE NOT NULL,
                    number     TEXT,
                    otp        TEXT,
                    service    TEXT,
                    sms        TEXT,
                    range_name TEXT,
                    added_at   TEXT    DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS traffic (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    range_name  TEXT,
                    number      TEXT,
                    cli         TEXT,
                    sms         TEXT,
                    otp         TEXT,
                    service     TEXT,
                    received_at TEXT
                );
                CREATE TABLE IF NOT EXISTS numbers (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    country  TEXT    NOT NULL,
                    number   TEXT    NOT NULL,
                    service  TEXT    DEFAULT 'All',
                    is_used  INTEGER DEFAULT 0,
                    used_by  INTEGER DEFAULT NULL,
                    use_date TEXT    DEFAULT NULL,
                    UNIQUE(number)
                );
                CREATE TABLE IF NOT EXISTS cooldowns (
                    user_id   INTEGER PRIMARY KEY,
                    timestamp INTEGER
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id  INTEGER,
                    message    TEXT,
                    total      INTEGER DEFAULT 0,
                    success    INTEGER DEFAULT 0,
                    failed     INTEGER DEFAULT 0,
                    sent_at    TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_otp_hash     ON otp_history(hash);
                CREATE INDEX IF NOT EXISTS idx_otp_added    ON otp_history(added_at);
                CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic(received_at);
                CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
                CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
                CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
                CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
            """)
            self._conn.commit()

    def get_setting(self, key, default=""):
        row = self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


db = Database(DB_FILE)


def get_country_info(number):
    clean = re.sub(r"\D", "", str(number))
    for length in (3, 2, 1):
        prefix = clean[:length]
        if prefix in COUNTRY_CODES:
            name, flag = COUNTRY_CODES[prefix]
            return name, flag
    return "Unknown", "🌐"


def get_country_display(number):
    name, flag = get_country_info(number)
    return f"{flag} {name}"


def mask_number(number):
    clean = re.sub(r"\D", "", str(number))
    if len(clean) >= 9:
        return f"+{clean[:5]}XXXX{clean[-4:]}"
    if len(clean) >= 6:
        return f"+{clean[:3]}XXX{clean[-3:]}"
    return f"+{clean}XXXX"


def extract_otp(sms):
    if not sms:
        return None
    for pattern in (
        r"\b\d{3}[-\s]\d{3}\b",
        r"\b\d{6,8}\b",
        r"\b\d{4,5}\b",
    ):
        m = re.search(pattern, sms)
        if m:
            return m.group().strip()
    return None


def detect_service(cli, sms):
    combined = f"{cli} {sms}".lower()
    if "whatsapp" in combined:
        return "WhatsApp"
    if "telegram" in combined:
        return "Telegram"
    if "instagram" in combined:
        return "Instagram"
    if "facebook" in combined or "fb" in combined:
        return "Facebook"
    if "google" in combined:
        return "Google"
    if "tiktok" in combined:
        return "TikTok"
    if "twitter" in combined or "x.com" in combined:
        return "Twitter/X"
    if "snapchat" in combined:
        return "Snapchat"
    if "discord" in combined:
        return "Discord"
    if "binance" in combined:
        return "Binance"
    if "bybit" in combined:
        return "Bybit"
    if "okx" in combined:
        return "OKX"
    if "coinbase" in combined:
        return "Coinbase"
    return cli.strip() if cli.strip() else "Unknown"


def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_flooded(user_id):
    if is_admin(user_id):
        return False
    now     = time.time()
    history = [t for t in flood_data.get(user_id, []) if now - t < FLOOD_WINDOW]
    history.append(now)
    flood_data[user_id] = history
    return len(history) > FLOOD_LIMIT


def register_user(user):
    existing = db.fetchone("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not existing:
        db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user.id, user.username or "", user.first_name or ""),
        )
    db.execute(
        "UPDATE users SET username=?, first_name=? WHERE user_id=?",
        (user.username or "", user.first_name or "", user.id),
    )


def is_banned(user_id):
    row = db.fetchone("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    return bool(row and row["is_banned"])


async def check_membership(bot, user_id):
    if is_admin(user_id):
        return True
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "banned"):
                return False
        except Exception:
            return False
    return True


def check_number_cooldown(user_id):
    row = db.fetchone("SELECT timestamp FROM cooldowns WHERE user_id=?", (user_id,))
    if row:
        elapsed = int(time.time()) - row["timestamp"]
        if elapsed < NUMBER_COOLDOWN:
            return NUMBER_COOLDOWN - elapsed
    return 0


def set_number_cooldown(user_id):
    db.execute(
        "INSERT OR REPLACE INTO cooldowns (user_id, timestamp) VALUES (?, ?)",
        (user_id, int(time.time())),
    )


def extract_numbers_from_content(content, filename):
    nums = set()
    try:
        if filename.endswith(".xlsx"):
            wb = openpyxl.load_workbook(BytesIO(bytes(content)), read_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell:
                            val = re.sub(r"\D", "", str(cell))
                            if 7 <= len(val) <= 15:
                                nums.add(val)
        else:
            text = content.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                val = re.sub(r"\D", "", line.strip())
                if 7 <= len(val) <= 15:
                    nums.add(val)
    except Exception as e:
        logger.error(f"Number extraction error: {e}")
    return list(nums)


def join_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Main Channel", url=MAIN_CHANNEL_LINK),
            InlineKeyboardButton("💬 OTP Group", url=OTP_GROUP_LINK),
        ],
        [InlineKeyboardButton("📡 Backup Channel", url=BACKUP_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I've Joined — Verify", callback_data="check_join")],
    ])


def main_menu_reply(user_id=None):
    if user_id and is_admin(user_id):
        return ReplyKeyboardMarkup(
            [[KeyboardButton("≡ Menu"), KeyboardButton("⚙️ Admin")]],
            resize_keyboard=True,
            one_time_keyboard=False,
        )
    return ReplyKeyboardMarkup(
        [[KeyboardButton("≡ Menu")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def main_menu_inline(user_id=None):
    buttons = [
        [
            InlineKeyboardButton("📡 Live OTPs", url=OTP_GROUP_LINK),
            InlineKeyboardButton("📢 Channel", url=MAIN_CHANNEL_LINK),
        ],
        [
            InlineKeyboardButton("🌍 Get Number", callback_data="menu_get_number"),
            InlineKeyboardButton("📡 Backup", url=BACKUP_CHANNEL_LINK),
        ],
        [
            InlineKeyboardButton("📊 Traffic", callback_data="menu_traffic"),
            InlineKeyboardButton("ℹ️ About", callback_data="menu_about"),
        ],
    ]
    if user_id and is_admin(user_id):
        buttons.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(buttons)


def otp_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Channel", url=MAIN_CHANNEL_LINK),
            InlineKeyboardButton("📡 Backup", url=BACKUP_CHANNEL_LINK),
        ],
        [InlineKeyboardButton(f"🤖 {BOT_NAME}", url=BOT_LINK)],
    ])


def admin_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton("🌍 Add Numbers", callback_data="adm_numbers"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="adm_stats"),
            InlineKeyboardButton("🔄 Worker", callback_data="adm_worker"),
        ],
        [
            InlineKeyboardButton("🔧 Maintenance", callback_data="adm_toggle_maint"),
            InlineKeyboardButton("📋 Traffic Log", callback_data="adm_traffic"),
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")],
    ])


def admin_text():
    total_users = db.fetchone("SELECT COUNT(*) AS c FROM users")["c"]
    total_otps  = db.fetchone("SELECT COUNT(*) AS c FROM otp_history")["c"]
    today_str   = datetime.now().strftime("%Y-%m-%d")
    today_otps  = db.fetchone(
        "SELECT COUNT(*) AS c FROM otp_history WHERE added_at LIKE ?",
        (f"{today_str}%",),
    )["c"]
    total_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
    avail_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
    status = "🟢 Online" if worker_info["logged_in"] else "🔴 Offline"
    maint  = "🔧 ON" if maintenance else "✅ OFF"
    return (
        f"╭─⟦ 𝐀𝐃𝐌𝐈𝐍 ⟧─⊷\n"
        f"┃\n"
        f"┃ ⦿ 𝐔𝐒𝐄𝐑𝐒    : {total_users}\n"
        f"┃ ⦿ 𝐎𝐓𝐏𝐒     : {total_otps}\n"
        f"┃ ⦿ 𝐓𝐎𝐃𝐀𝐘    : {today_otps}\n"
        f"┃ ⦿ 𝐍𝐔𝐌𝐁𝐄𝐑𝐒  : {avail_nums} free / {total_nums}\n"
        f"┃ ⦿ 𝐖𝐎𝐑𝐊𝐄𝐑   : {status}\n"
        f"┃ ⦿ 𝐋𝐀𝐒𝐓 𝐎𝐓𝐏 : {worker_info['last_otp']}\n"
        f"┃ ⦿ 𝐌𝐀𝐈𝐍𝐓    : {maint}\n"
        f"┃\n"
        f"╰━━━━━━━━━━━⊷"
    )


def back_to_menu():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    )


def back_to_admin():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")]]
    )


def back_to_numbers():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")],
        [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
    ])


def cancel_state_markup(back_cb="adm_back"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_state"),
            InlineKeyboardButton("⬅️ Back", callback_data=back_cb),
        ]
    ])


def build_service_grid():
    rows = db.fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=0 GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        label = f"{r['service']} ({r['cnt']})"
        cb    = f"gns__{r['service']}"
        row_buf.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_back")])
    return rows, InlineKeyboardMarkup(buttons)


def build_country_grid_for_service(service):
    rows = db.fetchall(
        "SELECT country, COUNT(*) AS cnt FROM numbers WHERE is_used=0 AND service=? "
        "GROUP BY country ORDER BY country",
        (service,),
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        label = f"{r['country']} ({r['cnt']})"
        cb    = f"gnc__{r['country']}__{service}"
        row_buf.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([InlineKeyboardButton("⬅️ Back to Services", callback_data="menu_get_number")])
    return rows, InlineKeyboardMarkup(buttons)


def _service_picker_markup(mode="file"):
    buttons = []
    row_buf = []
    for svc in DEFAULT_SERVICES:
        row_buf.append(InlineKeyboardButton(svc, callback_data=f"adm_svc__{svc}"))
        if len(row_buf) == 3:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([InlineKeyboardButton("✏️ Custom Service", callback_data=f"adm_svc_custom__{mode}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_state")])
    return InlineKeyboardMarkup(buttons)


async def send_with_banner(bot, chat_id, text, reply_markup=None, disable_web_page_preview=False):
    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=BANNER_URL,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    except Exception:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )


async def edit_with_banner(query, text, reply_markup=None, disable_web_page_preview=False):
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=BANNER_URL,
                caption=text,
                parse_mode=ParseMode.HTML,
            ),
            reply_markup=reply_markup,
        )
    except Exception:
        try:
            await query.edit_message_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                )
            except Exception:
                pass


async def notify_admins(app, text):
    for aid in ADMIN_IDS:
        try:
            await app.bot.send_photo(
                aid,
                photo=BANNER_URL,
                caption=text,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            try:
                await app.bot.send_message(aid, text, parse_mode=ParseMode.HTML)
            except Exception:
                pass


def _make_ssl_context():
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        return ctx
    except Exception:
        ctx = ssl.create_default_context()
        return ctx


def solve_captcha(html):
    try:
        soup      = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text(" ", strip=True)
        m = re.search(
            r"[Ww]hat\s+is\s+(\d+)\s*([+\-*×xX÷/])\s*(\d+)\s*[=?]",
            full_text,
        )
        if not m:
            for tag in soup.find_all(True):
                t = tag.get_text(strip=True)
                m = re.search(r"(\d+)\s*([+\-*×xX÷/])\s*(\d+)\s*=\s*\?", t)
                if m:
                    break
        if m:
            a  = int(m.group(1))
            op = m.group(2).strip()
            b  = int(m.group(3))
            if op == "+":
                return str(a + b)
            if op == "-":
                return str(a - b)
            if op in ("*", "×", "x", "X"):
                return str(a * b)
            if op in ("÷", "/") and b != 0:
                return str(a // b)
    except Exception as e:
        logger.error(f"Captcha solve error: {e}")
    return "0"


class PanelSession:
    def __init__(self):
        self._session   = None
        self._logged_in = False

    async def _get_session(self):
        if self._session is None or self._session.closed:
            ssl_ctx   = _make_ssl_context()
            connector = aiohttp.TCPConnector(
                ssl=ssl_ctx,
                limit=10,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                    ),
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
                timeout=aiohttp.ClientTimeout(total=60, connect=20),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
        return self._session

    async def login(self):
        try:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None

            sess = await self._get_session()

            login_html = ""
            try:
                async with sess.get(
                    PANEL_LOGIN_PAGE,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    login_html = await resp.text(errors="replace")
                    logger.info(f"Login page: status={resp.status}, url={resp.url}")
            except Exception as e:
                logger.error(f"Login page fetch error: {e}")
                return False

            if not login_html:
                logger.error("Empty login page")
                return False

            soup = BeautifulSoup(login_html, "html.parser")

            etkk = ""
            etkk_inp = soup.find("input", {"name": "etkk"})
            if etkk_inp:
                etkk = etkk_inp.get("value", "")
            if not etkk:
                m = re.search(r'name=["\']etkk["\'][^>]*value=["\']([^"\']+)["\']', login_html)
                if not m:
                    m = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']etkk["\']', login_html)
                if m:
                    etkk = m.group(1)

            capt = solve_captcha(login_html)
            logger.info(f"etkk={etkk[:10] if etkk else 'not found'}, capt={capt}")

            form_data = aiohttp.FormData()
            if etkk:
                form_data.add_field("etkk", etkk)
            form_data.add_field("username", PANEL_USERNAME)
            form_data.add_field("password", PANEL_PASSWORD)
            form_data.add_field("capt", capt)

            try:
                async with sess.post(
                    PANEL_SIGNIN_URL,
                    data=form_data,
                    headers={
                        "Referer": PANEL_LOGIN_PAGE,
                        "Origin": PANEL_BASE,
                        "Sec-Fetch-Site": "same-origin",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-User": "?1",
                        "Sec-Fetch-Dest": "document",
                    },
                    allow_redirects=True,
                    max_redirects=10,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    final_url = str(resp.url).lower()
                    body      = await resp.text(errors="replace")
                    logger.info(f"Signin: status={resp.status}, url={final_url}, body_len={len(body)}")

                    if "login" not in final_url and resp.status in (200, 302):
                        self._logged_in = True
                        logger.info(f"Panel login OK → {final_url}")
                        return True
                    if any(w in final_url for w in ("dashboard", "client", "agent", "sms")):
                        self._logged_in = True
                        logger.info(f"Panel login OK (redirect) → {final_url}")
                        return True
                    if resp.status == 200 and "login" not in final_url:
                        self._logged_in = True
                        return True

                    logger.error(f"Login failed | url={final_url} | status={resp.status}")
                    return False

            except Exception as e:
                logger.error(f"Signin POST error: {e}")
                return False

        except Exception as e:
            logger.error(f"Login exception: {type(e).__name__}: {e}")
            return False

    async def keepalive(self):
        try:
            sess = await self._get_session()
            async with sess.get(
                PANEL_DASHBOARD_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                final_url = str(resp.url).lower()
                if "login" in final_url:
                    self._logged_in = False
                    logger.warning("Keepalive: session expired")
                    return False
                logger.info(f"Keepalive OK: {final_url}")
                return True
        except Exception as e:
            logger.error(f"Keepalive error: {e}")
            return False

    async def fetch_cdr(self):
        try:
            sess = await self._get_session()
            now       = datetime.now()
            date_from = now.strftime("%Y-%m-%d 00:00:00")
            date_to   = now.strftime("%Y-%m-%d 23:59:59")
            fdate1    = now.strftime("%Y-%m-%d%%2000:00")
            fdate2    = now.strftime("%Y-%m-%d%%2023:59:59")

            async with sess.get(
                PANEL_CDR_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=40),
            ) as resp:
                final_url = str(resp.url).lower()
                if "login" in final_url:
                    self._logged_in = False
                    return None, "session_expired"
                page_html = await resp.text(errors="replace")

            soup = BeautifulSoup(page_html, "html.parser")
            form = soup.find("form")

            if form:
                form_data  = {}
                action     = form.get("action") or PANEL_CDR_URL
                method     = (form.get("method") or "get").lower()
                if not action.startswith("http"):
                    action = PANEL_BASE + "/" + action.lstrip("/")

                for inp in form.find_all(["input", "select", "textarea"]):
                    name = inp.get("name")
                    if not name:
                        continue
                    itype = (inp.get("type") or "text").lower()
                    if itype in ("submit", "button", "reset", "image"):
                        continue
                    if itype == "checkbox" and not inp.get("checked"):
                        continue
                    val        = inp.get("value", "")
                    name_lower = name.lower()
                    if any(k in name_lower for k in ("from", "start", "begin", "date1", "dstart", "fdate1")):
                        val = date_from
                    elif any(k in name_lower for k in ("to", "end", "stop", "date2", "dend", "fdate2")):
                        val = date_to
                    form_data[name] = val

                if method == "post":
                    async with sess.post(
                        action,
                        data=form_data,
                        headers={
                            "Referer": PANEL_CDR_URL,
                            "Origin": PANEL_BASE,
                        },
                        allow_redirects=True,
                        timeout=aiohttp.ClientTimeout(total=40),
                    ) as r2:
                        if "login" in str(r2.url).lower():
                            self._logged_in = False
                            return None, "session_expired"
                        return await r2.text(errors="replace"), None
                else:
                    async with sess.get(
                        action,
                        params=form_data,
                        allow_redirects=True,
                        timeout=aiohttp.ClientTimeout(total=40),
                    ) as r2:
                        if "login" in str(r2.url).lower():
                            self._logged_in = False
                            return None, "session_expired"
                        return await r2.text(errors="replace"), None

            ajax_url = f"{PANEL_BASE}/client/res/data_smscdr.php"
            params   = {
                "fdate1": now.strftime("%Y-%m-%d 00:00"),
                "fdate2": now.strftime("%Y-%m-%d 23:59:59"),
            }
            async with sess.get(
                ajax_url,
                params=params,
                headers={"Referer": PANEL_CDR_URL, "X-Requested-With": "XMLHttpRequest"},
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=40),
            ) as r3:
                if "login" in str(r3.url).lower():
                    self._logged_in = False
                    return None, "session_expired"
                return await r3.text(errors="replace"), None

        except Exception as e:
            logger.error(f"Fetch CDR error: {e}")
            return None, str(e)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


panel = PanelSession()


def parse_sms_rows(html):
    rows = []
    try:
        soup   = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        target = None
        for t in tables:
            ths      = t.find_all("th")
            combined = " ".join(th.get_text(strip=True).lower() for th in ths)
            if "sms" in combined or ("number" in combined and ("cli" in combined or "range" in combined)):
                target = t
                break
        if not target and tables:
            target = tables[0]
        if not target:
            return rows
        header_row = target.find("tr")
        if not header_row:
            return rows
        headers = [c.get_text(strip=True).lower() for c in header_row.find_all(["th", "td"])]
        col = {}
        for i, h in enumerate(headers):
            if "date" in h and "date" not in col:
                col["date"] = i
            if "range" in h and "range" not in col:
                col["range"] = i
            if h == "number" and "number" not in col:
                col["number"] = i
            if h == "cli" and "cli" not in col:
                col["cli"] = i
            if h == "sms" and "sms" not in col:
                col["sms"] = i

        def safe_col(cells, key, fallback):
            idx = col.get(key, fallback)
            if idx < len(cells):
                return cells[idx].get_text(strip=True)
            return ""

        for tr in target.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            row = {
                "date":   safe_col(cells, "date",   0),
                "range":  safe_col(cells, "range",  1),
                "number": safe_col(cells, "number", 2),
                "cli":    safe_col(cells, "cli",    3),
                "sms":    safe_col(cells, "sms",    4),
            }
            if row["number"] or row["sms"]:
                rows.append(row)
    except Exception as e:
        logger.error(f"Parse rows error: {e}")
    return rows


def format_otp_message(row, otp, service):
    masked  = mask_number(row["number"])
    country_name, country_flag = get_country_info(row["number"])
    sms_txt = (row.get("sms") or "").strip()

    text = (
        f"╭─⟦ <b>ᴍʀ.ᴀғʀɪx ᴏᴛᴘ</b> ⟧─⊷\n"
        f"┃\n"
        f"┃ ⦿ 𝐎𝐓𝐏     : <code>{otp}</code>\n"
        f"┃ ⦿ 𝐒𝐄𝐑𝐕𝐈𝐂𝐄 : {service}\n"
        f"┃ ⦿ 𝐂𝐎𝐔𝐍𝐓𝐑𝐘 : {country_flag} {country_name}\n"
        f"┃ ⦿ 𝐍𝐔𝐌𝐁𝐄𝐑  : <code>{masked}</code>\n"
        f"┃\n"
        f"╰━━━━━━━━━━━⊷\n\n"
        f"<blockquote>{sms_txt}</blockquote>"
    )
    return text, otp_buttons()


async def sms_worker(app):
    global maintenance
    worker_info["running"] = True
    keepalive_timer        = 0
    last_reset_day         = datetime.now().day

    while True:
        try:
            today = datetime.now().day
            if today != last_reset_day:
                worker_info["otps_today"] = 0
                last_reset_day            = today

            if not panel._logged_in:
                worker_info["logged_in"] = False
                logger.info("Attempting panel login...")
                ok = await panel.login()
                if not ok:
                    worker_info["errors"] += 1
                    await notify_admins(
                        app,
                        f"❌ <b>Panel Login Failed</b>\n"
                        f"Attempt #{worker_info['errors']}. Retrying in 30s...",
                    )
                    await asyncio.sleep(30)
                    continue
                worker_info["logged_in"]  = True
                worker_info["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worker_info["errors"]     = 0
                await notify_admins(
                    app,
                    f"✅ <b>Panel Login Successful</b>\n"
                    f"{BOT_NAME} is live and monitoring.",
                )

            keepalive_timer += POLL_INTERVAL
            if keepalive_timer >= KEEPALIVE_INTERVAL:
                alive = await panel.keepalive()
                if not alive:
                    panel._logged_in         = False
                    worker_info["logged_in"] = False
                    await notify_admins(app, "⚠️ <b>Session Expired</b>\nRe-authenticating...")
                keepalive_timer = 0

            html, err = await panel.fetch_cdr()

            if err == "session_expired":
                panel._logged_in         = False
                worker_info["logged_in"] = False
                await notify_admins(app, "⚠️ <b>Session Expired</b>\nRe-authenticating...")
                continue

            if err:
                logger.warning(f"Fetch warning: {err}")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if html:
                for row in parse_sms_rows(html):
                    try:
                        sms    = (row.get("sms")    or "").strip()
                        number = (row.get("number") or "").strip()
                        date   = (row.get("date")   or "").strip()
                        cli    = (row.get("cli")    or "").strip()

                        if not sms or not number:
                            continue
                        if not re.sub(r"[Xx\s\-_*]", "", sms):
                            continue

                        otp = extract_otp(sms)
                        if not otp:
                            continue

                        service = detect_service(cli, sms)

                        h = hashlib.md5(f"{date}{number}{sms}".encode()).hexdigest()

                        if h in otp_cache:
                            continue
                        if db.fetchone("SELECT id FROM otp_history WHERE hash=?", (h,)):
                            otp_cache.add(h)
                            continue

                        text_msg, markup = format_otp_message(row, otp, service)

                        await app.bot.send_photo(
                            chat_id=OTP_GROUP_ID,
                            photo=BANNER_URL,
                            caption=text_msg,
                            parse_mode=ParseMode.HTML,
                            reply_markup=markup,
                        )

                        otp_cache.add(h)
                        db.execute(
                            "INSERT OR IGNORE INTO otp_history "
                            "(hash, number, otp, service, sms, range_name) VALUES (?,?,?,?,?,?)",
                            (h, number, otp, service, sms, row.get("range", "")),
                        )
                        db.execute(
                            "INSERT INTO traffic "
                            "(range_name, number, cli, sms, otp, service, received_at) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (
                                row.get("range", ""),
                                number,
                                cli,
                                sms,
                                otp,
                                service,
                                date,
                            ),
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                        logger.info(f"OTP sent | {mask_number(number)} | {otp} | {service}")

                    except Exception as row_err:
                        logger.error(f"Row error: {row_err}")
                        continue

            await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as e:
            worker_info["errors"] += 1
            logger.error(f"Worker loop error: {e}")
            if worker_info["errors"] % 5 == 0:
                await notify_admins(
                    app,
                    f"🚨 <b>Worker Error</b>\n<code>{e}</code>\nAuto-recovering...",
                )
            await asyncio.sleep(15)

    worker_info["running"] = False


BANNED_TEXT = "🚫 You have been banned from using this bot."
MAINT_TEXT  = "🔧 Bot is under maintenance. Please check back soon."
JOIN_TEXT   = (
    f"👋 <b>Welcome to {BOT_NAME}!</b>\n\n"
    f"⚠️ You must join our channels before using the bot.\n"
    f"Please join all channels below then tap <b>Verify</b>:"
)
WELCOME_TEXT = (
    f"╭─⟦ <b>ᴍʀ.ᴀғʀɪx</b> ⟧─⊷\n"
    f"┃\n"
    f"┃  Welcome to MR.AFRIX OTP Bot\n"
    f"┃  Live OTP monitoring 24/7\n"
    f"┃\n"
    f"╰━━━━━━━━━━━⊷"
)
WELCOME_ADMIN_TEXT = (
    f"╭─⟦ <b>ᴍʀ.ᴀғʀɪx</b> ⟧─⊷\n"
    f"┃\n"
    f"┃  Welcome back, Admin\n"
    f"┃  Full access granted\n"
    f"┃\n"
    f"╰━━━━━━━━━━━⊷"
)


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    register_user(user)

    if is_admin(user.id):
        return True
    if is_banned(user.id):
        await send_with_banner(context.bot, update.effective_chat.id, BANNED_TEXT)
        return False
    if is_flooded(user.id):
        await send_with_banner(context.bot, update.effective_chat.id, "⚠️ Slow down.")
        return False
    if maintenance:
        await send_with_banner(context.bot, update.effective_chat.id, MAINT_TEXT)
        return False
    joined = await check_membership(context.bot, user.id)
    if not joined:
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            JOIN_TEXT,
            reply_markup=join_markup(),
        )
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    if not is_admin(user.id):
        if is_banned(user.id):
            await send_with_banner(context.bot, update.effective_chat.id, BANNED_TEXT)
            return
        if is_flooded(user.id):
            await send_with_banner(context.bot, update.effective_chat.id, "⚠️ Slow down.")
            return
        if maintenance:
            await send_with_banner(context.bot, update.effective_chat.id, MAINT_TEXT)
            return
        joined = await check_membership(context.bot, user.id)
        if not joined:
            await send_with_banner(
                context.bot,
                update.effective_chat.id,
                JOIN_TEXT,
                reply_markup=join_markup(),
            )
            return

    await update.message.reply_text("✅", reply_markup=main_menu_reply(user.id))

    welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await send_with_banner(
        context.bot,
        update.effective_chat.id,
        welcome,
        reply_markup=main_menu_inline(user.id),
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await gate(update, context):
        return
    user      = update.effective_user
    w_status  = "🟢 Running" if worker_info["running"] else "🔴 Stopped"
    p_status  = "✅ Logged In" if worker_info["logged_in"] else "❌ Logged Out"
    maint     = "🔧 ON" if maintenance else "✅ OFF"
    total     = db.fetchone("SELECT COUNT(*) AS c FROM otp_history")["c"]
    today_s   = datetime.now().strftime("%Y-%m-%d")
    today_c   = db.fetchone(
        "SELECT COUNT(*) AS c FROM otp_history WHERE added_at LIKE ?",
        (f"{today_s}%",),
    )["c"]
    total_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
    avail_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
    await send_with_banner(
        context.bot,
        update.effective_chat.id,
        f"╭─⟦ <b>𝐒𝐓𝐀𝐓𝐔𝐒</b> ⟧─⊷\n"
        f"┃\n"
        f"┃ ⦿ 𝐖𝐎𝐑𝐊𝐄𝐑  : {w_status}\n"
        f"┃ ⦿ 𝐏𝐀𝐍𝐄𝐋   : {p_status}\n"
        f"┃ ⦿ 𝐌𝐀𝐈𝐍𝐓   : {maint}\n"
        f"┃ ⦿ 𝐓𝐎𝐓𝐀𝐋   : {total} OTPs\n"
        f"┃ ⦿ 𝐓𝐎𝐃𝐀𝐘   : {today_c} OTPs\n"
        f"┃ ⦿ 𝐍𝐔𝐌𝐒    : {avail_nums}/{total_nums}\n"
        f"┃ ⦿ 𝐋𝐀𝐒𝐓    : {worker_info['last_otp']}\n"
        f"┃\n"
        f"╰━━━━━━━━━━━⊷",
        reply_markup=back_to_menu(),
    )


async def traffic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await gate(update, context):
        return
    user = update.effective_user
    rows = db.fetchall(
        "SELECT range_name, number, sms, otp, service, received_at "
        "FROM traffic ORDER BY id DESC LIMIT 20"
    )
    if not rows:
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            "📭 No traffic recorded yet.",
            reply_markup=back_to_menu(),
        )
        return
    lines = ["╭─⟦ <b>𝐋𝐈𝐕𝐄 𝐓𝐑𝐀𝐅𝐅𝐈𝐂</b> ⟧─⊷\n┃"]
    for r in rows:
        masked       = mask_number(r["number"])
        country_name, flag = get_country_info(r["number"])
        otp_val      = r["otp"] or extract_otp(r["sms"] or "") or "—"
        service      = r["service"] or "—"
        lines.append(
            f"┃ {flag} <code>{masked}</code> | {service} | <b>{otp_val}</b> | {r['received_at'] or '—'}"
        )
    lines.append("┃\n╰━━━━━━━━━━━⊷")
    await send_with_banner(
        context.bot,
        update.effective_chat.id,
        "\n".join(lines),
        reply_markup=back_to_menu(),
    )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await send_with_banner(
        context.bot,
        update.effective_chat.id,
        admin_text(),
        reply_markup=admin_markup(),
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE.pop(user.id, None)
    await send_with_banner(
        context.bot,
        update.effective_chat.id,
        "❌ Action cancelled.",
        reply_markup=main_menu_inline(user.id),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global maintenance
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    if not is_admin(user.id) and is_banned(user.id) and data != "check_join":
        await query.answer(BANNED_TEXT, show_alert=True)
        return

    if data == "check_join":
        joined = await check_membership(context.bot, user.id)
        if joined:
            register_user(user)
            welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_with_banner(query, welcome, reply_markup=main_menu_inline(user.id))
        else:
            await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        return

    if data == "menu_back":
        welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await edit_with_banner(query, welcome, reply_markup=main_menu_inline(user.id))
        return

    if data == "menu_admin":
        if not is_admin(user.id):
            await query.answer("⛔ Admins only.", show_alert=True)
            return
        await edit_with_banner(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "menu_about":
        total       = db.fetchone("SELECT COUNT(*) AS c FROM otp_history")["c"]
        total_nums  = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
        avail_nums  = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
        total_users = db.fetchone("SELECT COUNT(*) AS c FROM users")["c"]
        await edit_with_banner(
            query,
            f"╭─⟦ <b>ᴀʙᴏᴜᴛ</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ ⦿ 𝐁𝐎𝐓     : {BOT_NAME}\n"
            f"┃ ⦿ 𝐎𝐓𝐏𝐒    : {total}\n"
            f"┃ ⦿ 𝐍𝐔𝐌𝐁𝐄𝐑𝐒 : {avail_nums}/{total_nums}\n"
            f"┃ ⦿ 𝐔𝐒𝐄𝐑𝐒   : {total_users}\n"
            f"┃\n"
            f"╰━━━━━━━━━━━⊷",
            reply_markup=back_to_menu(),
        )
        return

    if data == "menu_traffic":
        if not is_admin(user.id) and is_flooded(user.id):
            await query.answer("⚠️ Slow down!", show_alert=True)
            return
        rows = db.fetchall(
            "SELECT range_name, number, sms, otp, service, received_at "
            "FROM traffic ORDER BY id DESC LIMIT 20"
        )
        if not rows:
            await edit_with_banner(query, "📭 No traffic recorded yet.", reply_markup=back_to_menu())
            return
        lines = ["╭─⟦ <b>𝐋𝐈𝐕𝐄 𝐓𝐑𝐀𝐅𝐅𝐈𝐂</b> ⟧─⊷\n┃"]
        for r in rows:
            masked           = mask_number(r["number"])
            country_name, flag = get_country_info(r["number"])
            otp_val          = r["otp"] or extract_otp(r["sms"] or "") or "—"
            service          = r["service"] or "—"
            lines.append(
                f"┃ {flag} <code>{masked}</code> | {service} | <b>{otp_val}</b> | {r['received_at'] or '—'}"
            )
        lines.append("┃\n╰━━━━━━━━━━━⊷")
        await edit_with_banner(query, "\n".join(lines), reply_markup=back_to_menu())
        return

    if data == "menu_get_number":
        if not is_admin(user.id) and maintenance:
            await query.answer(MAINT_TEXT, show_alert=True)
            return
        _, markup = build_service_grid()
        if markup is None:
            await edit_with_banner(
                query,
                "╭─⟦ <b>𝐍𝐔𝐌𝐁𝐄𝐑𝐒</b> ⟧─⊷\n┃\n┃  No numbers available right now\n┃  Check back soon!\n┃\n╰━━━━━━━━━━━⊷",
                reply_markup=back_to_menu(),
            )
            return
        await edit_with_banner(
            query,
            "╭─⟦ <b>𝐆𝐄𝐓 𝐍𝐔𝐌𝐁𝐄𝐑</b> ⟧─⊷\n┃\n┃  Step 1 — Pick your service\n┃\n╰━━━━━━━━━━━⊷",
            reply_markup=markup,
        )
        return

    if data.startswith("gns__"):
        service = data.replace("gns__", "")
        _, markup = build_country_grid_for_service(service)
        if markup is None:
            await query.answer("❌ No numbers for this service!", show_alert=True)
            return
        await edit_with_banner(
            query,
            f"╭─⟦ <b>𝐆𝐄𝐓 𝐍𝐔𝐌𝐁𝐄𝐑</b> ⟧─⊷\n┃\n┃  Service: <b>{service}</b>\n┃  Step 2 — Pick your country\n┃\n╰━━━━━━━━━━━⊷",
            reply_markup=markup,
        )
        return

    if data.startswith("gnc__"):
        parts   = data.split("__", 2)
        country = parts[1]
        service = parts[2] if len(parts) > 2 else "All"

        wait = check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"⏳ Wait {wait}s before getting another number.", show_alert=True)
            return

        row = db.fetchone(
            "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
            (country, service),
        )
        if not row:
            await query.answer("❌ No numbers left for this slot!", show_alert=True)
            return

        num_id = row["id"]
        number = row["number"]

        updated = db.execute(
            "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=? AND is_used=0",
            (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
        ).rowcount

        if updated == 0:
            row2 = db.fetchone(
                "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
                (country, service),
            )
            if not row2:
                await query.answer("❌ No numbers left! Try again.", show_alert=True)
                return
            num_id = row2["id"]
            number = row2["number"]
            db.execute(
                "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=?",
                (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
            )

        if not is_admin(user.id):
            set_number_cooldown(user.id)

        country_name, country_flag = get_country_info(number)
        display    = f"+{number}" if not number.startswith("+") else number
        avail_left = db.fetchone(
            "SELECT COUNT(*) AS c FROM numbers WHERE country=? AND service=? AND is_used=0",
            (country, service),
        )["c"]

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"chgn__{country}__{service}__{num_id}")],
            [InlineKeyboardButton("💬 OTP Group", url=OTP_GROUP_LINK)],
            [InlineKeyboardButton("⬅️ Back to Countries", callback_data=f"gns__{service}")],
        ])

        await edit_with_banner(
            query,
            f"╭─⟦ <b>𝐘𝐎𝐔𝐑 𝐍𝐔𝐌𝐁𝐄𝐑</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ ⦿ 𝐍𝐔𝐌𝐁𝐄𝐑  : <code>{display}</code>\n"
            f"┃ ⦿ 𝐒𝐄𝐑𝐕𝐈𝐂𝐄 : {service}\n"
            f"┃ ⦿ 𝐂𝐎𝐔𝐍𝐓𝐑𝐘 : {country_flag} {country_name}\n"
            f"┃ ⦿ 𝐋𝐄𝐅𝐓    : {avail_left} remaining\n"
            f"┃\n"
            f"╰━━━━━━━━━━━⊷\n\n"
            f"<i>Tap the number to copy. Watch for OTP in the group.</i>",
            reply_markup=markup,
        )
        return

    if data.startswith("chgn__"):
        parts   = data.split("__")
        country = parts[1] if len(parts) > 1 else ""
        service = parts[2] if len(parts) > 2 else "All"
        old_id  = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

        wait = check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"⏳ Wait {wait}s before changing.", show_alert=True)
            return

        if old_id:
            db.execute("UPDATE numbers SET is_used=2 WHERE id=? AND used_by=?", (old_id, user.id))
        else:
            old = db.fetchone(
                "SELECT id FROM numbers WHERE country=? AND service=? AND used_by=? AND is_used=1",
                (country, service, user.id),
            )
            if old:
                db.execute("UPDATE numbers SET is_used=2 WHERE id=?", (old["id"],))

        row = db.fetchone(
            "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
            (country, service),
        )
        if not row:
            await query.answer("❌ No more numbers available!", show_alert=True)
            return

        num_id = row["id"]
        number = row["number"]

        updated = db.execute(
            "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=? AND is_used=0",
            (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
        ).rowcount

        if updated == 0:
            row2 = db.fetchone(
                "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
                (country, service),
            )
            if not row2:
                await query.answer("❌ No more numbers!", show_alert=True)
                return
            num_id = row2["id"]
            number = row2["number"]
            db.execute(
                "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=?",
                (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
            )

        if not is_admin(user.id):
            set_number_cooldown(user.id)

        country_name, country_flag = get_country_info(number)
        display    = f"+{number}" if not number.startswith("+") else number
        avail_left = db.fetchone(
            "SELECT COUNT(*) AS c FROM numbers WHERE country=? AND service=? AND is_used=0",
            (country, service),
        )["c"]

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"chgn__{country}__{service}__{num_id}")],
            [InlineKeyboardButton("💬 OTP Group", url=OTP_GROUP_LINK)],
            [InlineKeyboardButton("⬅️ Back to Countries", callback_data=f"gns__{service}")],
        ])

        await edit_with_banner(
            query,
            f"╭─⟦ <b>𝐍𝐔𝐌𝐁𝐄𝐑 𝐂𝐇𝐀𝐍𝐆𝐄𝐃</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ ⦿ 𝐍𝐔𝐌𝐁𝐄𝐑  : <code>{display}</code>\n"
            f"┃ ⦿ 𝐒𝐄𝐑𝐕𝐈𝐂𝐄 : {service}\n"
            f"┃ ⦿ 𝐂𝐎𝐔𝐍𝐓𝐑𝐘 : {country_flag} {country_name}\n"
            f"┃ ⦿ 𝐋𝐄𝐅𝐓    : {avail_left} remaining\n"
            f"┃\n"
            f"╰━━━━━━━━━━━⊷\n\n"
            f"<i>Tap the number to copy. Watch for OTP in the group.</i>",
            reply_markup=markup,
        )
        return

    if not is_admin(user.id):
        return

    if data == "adm_back":
        USER_STATE.pop(user.id, None)
        await edit_with_banner(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "adm_cancel_state":
        USER_STATE.pop(user.id, None)
        await edit_with_banner(query, "❌ <b>Action cancelled.</b>", reply_markup=admin_markup())
        return

    if data == "adm_toggle_maint":
        maintenance = not maintenance
        db.set_setting("maintenance", "1" if maintenance else "0")
        state = "enabled 🔧" if maintenance else "disabled ✅"
        await edit_with_banner(
            query,
            f"🔧 Maintenance mode <b>{state}</b>.",
            reply_markup=back_to_admin(),
        )
        return

    if data == "adm_stats":
        total_users   = db.fetchone("SELECT COUNT(*) AS c FROM users")["c"]
        banned_c      = db.fetchone("SELECT COUNT(*) AS c FROM users WHERE is_banned=1")["c"]
        total_otps    = db.fetchone("SELECT COUNT(*) AS c FROM otp_history")["c"]
        today_str     = datetime.now().strftime("%Y-%m-%d")
        today_otps    = db.fetchone(
            "SELECT COUNT(*) AS c FROM otp_history WHERE added_at LIKE ?",
            (f"{today_str}%",),
        )["c"]
        total_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
        avail_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
        used_nums  = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=1")["c"]
        w_status   = "🟢 Running" if worker_info["running"] else "🔴 Stopped"
        p_status   = "✅ Logged In" if worker_info["logged_in"] else "❌ Logged Out"
        await edit_with_banner(
            query,
            f"╭─⟦ <b>𝐒𝐓𝐀𝐓𝐒</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ ⦿ 𝐔𝐒𝐄𝐑𝐒   : {total_users} | banned: {banned_c}\n"
            f"┃ ⦿ 𝐎𝐓𝐏𝐒    : {total_otps} | today: {today_otps}\n"
            f"┃ ⦿ 𝐍𝐔𝐌𝐒    : {avail_nums} free / {used_nums} used / {total_nums} total\n"
            f"┃ ⦿ 𝐖𝐎𝐑𝐊𝐄𝐑  : {w_status}\n"
            f"┃ ⦿ 𝐏𝐀𝐍𝐄𝐋   : {p_status}\n"
            f"┃ ⦿ 𝐋𝐀𝐒𝐓    : {worker_info['last_otp']}\n"
            f"┃ ⦿ 𝐒𝐓𝐀𝐑𝐓   : {worker_info['started_at']}\n"
            f"┃\n"
            f"╰━━━━━━━━━━━⊷",
            reply_markup=back_to_admin(),
        )
        return

    if data == "adm_worker":
        w_status = "🟢 Running" if worker_info["running"] else "🔴 Stopped"
        p_status = "✅ Logged In" if worker_info["logged_in"] else "❌ Logged Out"
        await edit_with_banner(
            query,
            f"╭─⟦ <b>𝐖𝐎𝐑𝐊𝐄𝐑</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ ⦿ 𝐖𝐎𝐑𝐊𝐄𝐑    : {w_status}\n"
            f"┃ ⦿ 𝐏𝐀𝐍𝐄𝐋     : {p_status}\n"
            f"┃ ⦿ 𝐎𝐓𝐏𝐒 𝐓𝐎𝐃𝐀𝐘 : {worker_info['otps_today']}\n"
            f"┃ ⦿ 𝐋𝐀𝐒𝐓 𝐎𝐓𝐏   : {worker_info['last_otp']}\n"
            f"┃ ⦿ 𝐋𝐀𝐒𝐓 𝐋𝐎𝐆𝐈𝐍 : {worker_info['last_login']}\n"
            f"┃ ⦿ 𝐄𝐑𝐑𝐎𝐑𝐒     : {worker_info['errors']}\n"
            f"┃\n"
            f"╰━━━━━━━━━━━⊷",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Force Re-Login", callback_data="adm_relogin")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
            ]),
        )
        return

    if data == "adm_relogin":
        panel._logged_in         = False
        worker_info["logged_in"] = False
        worker_info["errors"]    = 0
        if panel._session and not panel._session.closed:
            await panel._session.close()
            panel._session = None
        await edit_with_banner(
            query,
            "🔁 <b>Re-login triggered.</b>\nWorker will re-authenticate on next cycle.",
            reply_markup=back_to_admin(),
        )
        return

    if data == "adm_broadcast":
        USER_STATE[user.id] = "BROADCAST"
        await edit_with_banner(
            query,
            "📢 <b>Broadcast</b>\n\n"
            "Send your message. HTML supported.\n\n"
            "Add inline buttons at the end:\n"
            "<code>[Label|https://url.com]</code>",
            reply_markup=cancel_state_markup("adm_back"),
        )
        return

    if data == "adm_traffic":
        rows = db.fetchall(
            "SELECT range_name, number, sms, otp, service, received_at "
            "FROM traffic ORDER BY id DESC LIMIT 20"
        )
        if not rows:
            await edit_with_banner(query, "📭 No traffic yet.", reply_markup=back_to_admin())
            return
        lines = ["╭─⟦ <b>𝐓𝐑𝐀𝐅𝐅𝐈𝐂 𝐋𝐎𝐆</b> ⟧─⊷\n┃"]
        for r in rows:
            masked           = mask_number(r["number"])
            country_name, flag = get_country_info(r["number"])
            otp_val          = r["otp"] or "—"
            service          = r["service"] or "—"
            lines.append(
                f"┃ {flag} <code>{masked}</code> | {service} | <b>{otp_val}</b> | {r['received_at'] or '—'}"
            )
        lines.append("┃\n╰━━━━━━━━━━━⊷")
        await edit_with_banner(
            query,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Export", callback_data="adm_export_traffic")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
            ]),
        )
        return

    if data == "adm_export_traffic":
        rows = db.fetchall(
            "SELECT range_name, number, cli, sms, otp, service, received_at FROM traffic"
        )
        lines = ["range_name,number,cli,sms,otp,service,received_at"]
        for r in rows:
            sms_clean = (r["sms"] or "").replace(",", " ")
            lines.append(
                f"{r['range_name']},{r['number']},{r['cli']},"
                f"{sms_clean},{r['otp']},{r['service']},{r['received_at']}"
            )
        data_bytes = "\n".join(lines).encode()
        await context.bot.send_document(
            chat_id=user.id,
            document=BytesIO(data_bytes),
            filename="traffic_export.csv",
            caption=f"📋 Traffic export — {len(rows)} records",
        )
        await query.answer("✅ Export sent!", show_alert=False)
        return

    if data == "adm_numbers":
        total_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
        avail_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
        used_nums  = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=1")["c"]
        slots = db.fetchall(
            "SELECT country, service, COUNT(*) AS cnt, "
            "SUM(CASE WHEN is_used=0 THEN 1 ELSE 0 END) AS free "
            "FROM numbers GROUP BY country, service ORDER BY country LIMIT 15"
        )
        lines = [
            f"╭─⟦ <b>𝐍𝐔𝐌𝐁𝐄𝐑𝐒 𝐃𝐁</b> ⟧─⊷\n"
            f"┃\n"
            f"┃ Total: <b>{total_nums}</b> | Free: <b>{avail_nums}</b> | Used: <b>{used_nums}</b>\n"
            f"┃\n"
            f"┃ <b>Slots:</b>"
        ]
        for r in slots:
            lines.append(f"┃ • {r['country']} [{r['service']}] — {r['free']}/{r['cnt']}")
        lines.append("┃\n╰━━━━━━━━━━━⊷")
        await edit_with_banner(
            query,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ Add Numbers", callback_data="adm_add_numbers"),
                    InlineKeyboardButton("🗑️ Remove Slot", callback_data="adm_remove_slot"),
                ],
                [InlineKeyboardButton("📥 Export", callback_data="adm_export_numbers")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
            ]),
        )
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_ADD_COUNTRY"
        await edit_with_banner(
            query,
            "🌍 <b>Add Numbers — Step 1</b>\n\nSend the <b>country name</b>:\n<i>Example: Ghana</i>",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if data == "adm_remove_slot":
        slots = db.fetchall(
            "SELECT country, service, COUNT(*) AS cnt FROM numbers "
            "GROUP BY country, service ORDER BY country"
        )
        if not slots:
            await query.answer("No slots in database.", show_alert=True)
            return
        buttons = []
        for r in slots:
            label = f"{r['country']} [{r['service']}] ({r['cnt']})"
            cb    = f"adm_delslot__{r['country']}__{r['service']}"
            buttons.append([InlineKeyboardButton(label, callback_data=cb)])
        buttons.append([InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")])
        await edit_with_banner(
            query,
            "🗑️ <b>Select slot to delete:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if data.startswith("adm_delslot__"):
        parts   = data.split("__", 2)
        country = parts[1]
        service = parts[2] if len(parts) > 2 else "All"
        deleted = db.execute(
            "DELETE FROM numbers WHERE country=? AND service=?", (country, service)
        ).rowcount
        await edit_with_banner(
            query,
            f"🗑️ Deleted <b>{deleted}</b> numbers from <b>{country} [{service}]</b>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
            ]),
        )
        return

    if data == "adm_export_numbers":
        rows = db.fetchall(
            "SELECT country, service, number, is_used, used_by, use_date FROM numbers ORDER BY country"
        )
        lines = ["country,service,number,is_used,used_by,use_date"]
        for r in rows:
            lines.append(
                f"{r['country']},{r['service']},{r['number']},"
                f"{r['is_used']},{r['used_by'] or ''},{r['use_date'] or ''}"
            )
        data_bytes = "\n".join(lines).encode()
        await context.bot.send_document(
            chat_id=user.id,
            document=BytesIO(data_bytes),
            filename="numbers_export.csv",
            caption=f"🌍 Numbers export — {len(rows)} numbers",
        )
        await query.answer("✅ Export sent!", show_alert=False)
        return

    if data.startswith("adm_svc__"):
        service = data.replace("adm_svc__", "")
        state   = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_FILE_SVC__"):
            country = state.replace("ADM_ADD_FILE_SVC__", "")
            USER_STATE[user.id] = f"WAITING_FILE__{country}__{service}"
            await send_with_banner(
                context.bot,
                user.id,
                f"✅ Country: <b>{country}</b>\n"
                f"⚙️ Service: <b>{service}</b>\n\n"
                f"Now send the <b>.txt</b>, <b>.csv</b>, or <b>.xlsx</b> file:",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        elif state.startswith("ADM_ADD_TYPE_SVC__"):
            country = state.replace("ADM_ADD_TYPE_SVC__", "")
            USER_STATE[user.id] = f"TYPING_NUMBERS__{country}__{service}"
            await send_with_banner(
                context.bot,
                user.id,
                f"✅ Country: <b>{country}</b>\n"
                f"⚙️ Service: <b>{service}</b>\n\n"
                f"Now send the numbers, one per line:",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        return

    if data in ("adm_svc_custom__file", "adm_svc_custom__type"):
        mode  = "file" if "file" in data else "type"
        state = USER_STATE.get(user.id, "")
        if mode == "file" and state.startswith("ADM_ADD_FILE_SVC__"):
            country = state.replace("ADM_ADD_FILE_SVC__", "")
            USER_STATE[user.id] = f"ADM_CUSTOM_SVC_FILE__{country}"
            await send_with_banner(
                context.bot,
                user.id,
                f"✍️ Type your <b>custom service name</b> for <b>{country}</b>:",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        elif mode == "type" and state.startswith("ADM_ADD_TYPE_SVC__"):
            country = state.replace("ADM_ADD_TYPE_SVC__", "")
            USER_STATE[user.id] = f"ADM_CUSTOM_SVC_TYPE__{country}"
            await send_with_banner(
                context.bot,
                user.id,
                f"✍️ Type your <b>custom service name</b> for <b>{country}</b>:",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        return

    if data == "adm_addmethod_file":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_METHOD__"):
            country = state.replace("ADM_ADD_METHOD__", "")
            USER_STATE[user.id] = f"ADM_ADD_FILE_SVC__{country}"
            await send_with_banner(
                context.bot,
                user.id,
                f"🌍 Country: <b>{country}</b>\n\n⚙️ Select service for this file:",
                reply_markup=_service_picker_markup("file"),
            )
        return

    if data == "adm_addmethod_type":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_METHOD__"):
            country = state.replace("ADM_ADD_METHOD__", "")
            USER_STATE[user.id] = f"ADM_ADD_TYPE_SVC__{country}"
            await send_with_banner(
                context.bot,
                user.id,
                f"🌍 Country: <b>{country}</b>\n\n⚙️ Select service:",
                reply_markup=_service_picker_markup("type"),
            )
        return


def _parse_broadcast_buttons(text):
    lines     = text.strip().splitlines()
    msg_lines = []
    buttons   = []
    btn_row   = []
    for line in lines:
        m = re.match(r"^\[([^\|]+)\|([^\]]+)\]$", line.strip())
        if m:
            label = m.group(1).strip()
            url   = m.group(2).strip()
            btn_row.append(InlineKeyboardButton(label, url=url))
            if len(btn_row) == 2:
                buttons.append(btn_row)
                btn_row = []
        else:
            if btn_row:
                buttons.append(btn_row)
                btn_row = []
            msg_lines.append(line)
    if btn_row:
        buttons.append(btn_row)
    msg_lines.append(f"\n\n🤖 <a href='{BOT_LINK}'>{BOT_NAME}</a>")
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return "\n".join(msg_lines), markup


async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global maintenance
    user = update.effective_user
    text = (update.message.text or "").strip()

    if text == "≡ Menu":
        register_user(user)
        if not is_admin(user.id):
            if is_banned(user.id):
                await send_with_banner(context.bot, update.effective_chat.id, BANNED_TEXT)
                return
            if is_flooded(user.id):
                await send_with_banner(context.bot, update.effective_chat.id, "⚠️ Slow down.")
                return
            if maintenance:
                await send_with_banner(context.bot, update.effective_chat.id, MAINT_TEXT)
                return
            joined = await check_membership(context.bot, user.id)
            if not joined:
                await send_with_banner(
                    context.bot,
                    update.effective_chat.id,
                    JOIN_TEXT,
                    reply_markup=join_markup(),
                )
                return
        welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            welcome,
            reply_markup=main_menu_inline(user.id),
        )
        return

    if text == "⚙️ Admin":
        if not is_admin(user.id):
            return
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            admin_text(),
            reply_markup=admin_markup(),
        )
        return

    if not is_admin(user.id):
        if is_banned(user.id):
            await send_with_banner(context.bot, update.effective_chat.id, BANNED_TEXT)
            return
        if is_flooded(user.id):
            await send_with_banner(context.bot, update.effective_chat.id, "⚠️ You're sending too fast.")
            return

    state = USER_STATE.get(user.id)
    if not state:
        return

    if state == "BROADCAST":
        if not is_admin(user.id):
            return
        all_users       = db.fetchall("SELECT user_id FROM users WHERE is_banned=0")
        broadcast_msg, broadcast_markup = _parse_broadcast_buttons(text)
        success, failed = 0, 0
        status_msg      = await send_with_banner(
            context.bot,
            update.effective_chat.id,
            f"📢 Broadcasting to {len(all_users)} users...",
        )
        for u in all_users:
            try:
                await context.bot.send_photo(
                    chat_id=u["user_id"],
                    photo=BANNER_URL,
                    caption=broadcast_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=broadcast_markup,
                )
                success += 1
                await asyncio.sleep(0.05)
            except Exception:
                try:
                    await context.bot.send_message(
                        chat_id=u["user_id"],
                        text=broadcast_msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=broadcast_markup,
                        disable_web_page_preview=True,
                    )
                    success += 1
                except Exception:
                    failed += 1
        USER_STATE.pop(user.id, None)
        db.execute(
            "INSERT INTO broadcasts (sender_id, message, total, success, failed) VALUES (?,?,?,?,?)",
            (user.id, text[:500], len(all_users), success, failed),
        )
        try:
            await context.bot.edit_message_caption(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                caption=(
                    f"📢 <b>Broadcast Complete</b>\n\n"
                    f"✅ Sent   : {success}\n"
                    f"❌ Failed : {failed}\n"
                    f"📊 Total  : {len(all_users)}"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=back_to_admin(),
            )
        except Exception:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=(
                        f"📢 <b>Broadcast Complete</b>\n\n"
                        f"✅ Sent   : {success}\n"
                        f"❌ Failed : {failed}\n"
                        f"📊 Total  : {len(all_users)}"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_to_admin(),
                )
            except Exception:
                pass
        return

    if state == "ADM_ADD_COUNTRY":
        if not is_admin(user.id):
            return
        country = text
        USER_STATE[user.id] = f"ADM_ADD_METHOD__{country}"
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            f"🌍 Country: <b>{country}</b>\n\nHow do you want to add numbers?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📁 Upload File", callback_data="adm_addmethod_file"),
                    InlineKeyboardButton("✏️ Type Numbers", callback_data="adm_addmethod_type"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_state")],
            ]),
        )
        return

    if state and state.startswith("ADM_ADD_METHOD__"):
        await send_with_banner(context.bot, update.effective_chat.id, "⏳ Use the buttons above.")
        return

    if state and state.startswith("ADM_CUSTOM_SVC_FILE__"):
        if not is_admin(user.id):
            return
        country = state.replace("ADM_CUSTOM_SVC_FILE__", "")
        service = text.strip()
        USER_STATE[user.id] = f"WAITING_FILE__{country}__{service}"
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            f"✅ Country: <b>{country}</b>\n⚙️ Service: <b>{service}</b>\n\nNow send the file:",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if state and state.startswith("ADM_CUSTOM_SVC_TYPE__"):
        if not is_admin(user.id):
            return
        country = state.replace("ADM_CUSTOM_SVC_TYPE__", "")
        service = text.strip()
        USER_STATE[user.id] = f"TYPING_NUMBERS__{country}__{service}"
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            f"✅ Country: <b>{country}</b>\n⚙️ Service: <b>{service}</b>\n\nNow send numbers, one per line:",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if state and state.startswith("TYPING_NUMBERS__"):
        if not is_admin(user.id):
            return
        parts   = state.replace("TYPING_NUMBERS__", "").split("__", 1)
        country = parts[0]
        service = parts[1] if len(parts) > 1 else "All"
        nums    = [
            re.sub(r"\D", "", line)
            for line in text.splitlines()
            if re.sub(r"\D", "", line.strip())
        ]
        nums    = [n for n in nums if 7 <= len(n) <= 15]
        count, dupes = 0, 0
        for n in nums:
            try:
                db.execute("INSERT INTO numbers (country, number, service) VALUES (?, ?, ?)", (country, n, service))
                count += 1
            except Exception:
                dupes += 1
        USER_STATE.pop(user.id, None)
        await send_with_banner(
            context.bot,
            update.effective_chat.id,
            f"✅ <b>Done!</b>\n🌍 Country: {country}\n⚙️ Service: {service}\n📥 Added: {count}\n♻️ Dupes: {dupes}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
            ]),
        )
        return


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    if not is_admin(user.id):
        return
    state = USER_STATE.get(user.id)
    if not state or not state.startswith("WAITING_FILE__"):
        return
    parts   = state.replace("WAITING_FILE__", "").split("__", 1)
    country = parts[0]
    service = parts[1] if len(parts) > 1 else "All"
    doc     = update.message.document
    if not doc.file_name.endswith((".txt", ".csv", ".xlsx")):
        await send_with_banner(context.bot, update.effective_chat.id, "❌ Invalid format. Use .txt, .csv, or .xlsx")
        return
    waiting = await send_with_banner(context.bot, update.effective_chat.id, "⏳ Processing file...")
    try:
        f       = await doc.get_file()
        content = await f.download_as_bytearray()
        nums    = extract_numbers_from_content(content, doc.file_name)
        count, dupes = 0, 0
        for n in nums:
            try:
                db.execute("INSERT INTO numbers (country, number, service) VALUES (?, ?, ?)", (country, n, service))
                count += 1
            except Exception:
                dupes += 1
        result_text = (
            f"✅ <b>File Processed!</b>\n"
            f"🌍 Country    : <b>{country}</b>\n"
            f"⚙️ Service    : <b>{service}</b>\n"
            f"📄 File       : <b>{doc.file_name}</b>\n"
            f"📥 Added      : <b>{count}</b>\n"
            f"♻️ Duplicates : <b>{dupes}</b>"
        )
        try:
            await context.bot.edit_message_caption(
                chat_id=update.effective_chat.id,
                message_id=waiting.message_id,
                caption=result_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")],
                    [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
                ]),
            )
        except Exception:
            await send_with_banner(
                context.bot,
                update.effective_chat.id,
                result_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Numbers", callback_data="adm_numbers")],
                    [InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_back")],
                ]),
            )
    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await send_with_banner(context.bot, update.effective_chat.id, "❌ Error processing file.")
    USER_STATE.pop(user.id, None)


async def health_handler(request):
    return web.Response(
        text=json.dumps({
            "status":     "ok",
            "bot":        BOT_NAME,
            "worker":     worker_info["running"],
            "logged_in":  worker_info["logged_in"],
            "otps_today": worker_info["otps_today"],
            "last_otp":   worker_info["last_otp"],
        }),
        content_type="application/json",
        status=200,
    )


async def post_init(application):
    global maintenance

    saved_maint = db.get_setting("maintenance")
    if saved_maint == "1":
        maintenance = True

    rows = db.fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
    for r in rows:
        otp_cache.add(r["hash"])
    logger.info(f"Loaded {len(otp_cache)} OTP hashes into cache")

    commands = [
        BotCommand("start",   "Start the bot"),
        BotCommand("traffic", "View recent OTP traffic"),
        BotCommand("status",  "View bot status"),
        BotCommand("admin",   "Admin panel"),
        BotCommand("cancel",  "Cancel current action"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered")

    app_web = web.Application()
    app_web.router.add_get("/",       health_handler)
    app_web.router.add_get("/health", health_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server on port {PORT}")

    application.create_task(sms_worker(application))
    logger.info(f"✅ {BOT_NAME} is fully live")


if __name__ == "__main__":
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    db.init()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start",   start))
    application.add_handler(CommandHandler("admin",   admin_cmd))
    application.add_handler(CommandHandler("traffic", traffic_cmd))
    application.add_handler(CommandHandler("status",  status_cmd))
    application.add_handler(CommandHandler("cancel",  cancel_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler)
    )

    logger.info(f"🚀 Starting {BOT_NAME}...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
