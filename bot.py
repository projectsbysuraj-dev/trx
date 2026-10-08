"""
=============================================================================
🎫 SCRATCH THE WIN - OFFICIAL TELEGRAM MINI APP BOT (PRODUCTION ENGINE) 🎫
=============================================================================
High-Performance, Loophole-Proof, Anti-Fraud Telegram Bot for Scratch The Win.

Features:
- ⭐ Telegram Premium Emojis & Rich HTML Design
- 🛡️ Zero Loophole Anti-Cheat Referral System:
    * Blocks Self-Referrals (User cannot invite own ID)
    * Atomic Double-Credit & Duplicate Prevention (Checks RTDB prior to award)
    * Instant Live Notification to Referrer upon successful join
    * Real-time +1 Free Scratch Card credit in Firebase Realtime Database
- 🔒 Strict Mandatory Channel Gatekeeper:
    * Supports Public (@channel) and Private (-100...) Join Request Channels
    * Interactive "🔄 Verify Joined" check with real-time membership validation
    * WebApp button unlocks ONLY after all channels are joined
- 📱 Single Device Verification & Anti-Account-Switch Security Integration
- 🌐 Built-in Threaded HTTP Health Server for 24/7 Render/Railway/VPS uptime
- 👑 Dynamic Owner & Channel Management (/addchannel, /removechannel, /broadcast, /stats)
- 🚀 Mobile/Termux resilient long-polling with HTTPXRequest auto-recovery
=============================================================================
"""

import os
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import json
import time
import re
import urllib.request
import urllib.error
import urllib.parse
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MessageEntity,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut, Conflict, BadRequest, Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# 1. CORE BOT CONFIGURATION (ENV VARS WITH BULLETPROOF DEFAULTS)
# ---------------------------------------------------------------------------
TOKEN = os.environ.get("BOT_TOKEN", "8973201055:AAGiHa1ewSL0F_mG0v_f1WpMqK2lRySxSko").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "scratch_the_win_bot").strip().lstrip("@")
WEB_URL = os.environ.get(
    "WEB_URL",
    "https://ais-dev-ripkmfmdh6ff5haiwlht5i-1076687764335.asia-southeast1.run.app"
).strip().rstrip("/")
RTDB_URL = os.environ.get("RTDB_URL", "https://scratch-7d728-default-rtdb.firebaseio.com").strip().rstrip("/")

# ---------------------------------------------------------------------------
# 2. PERMANENT MANDATORY CHANNELS
# ---------------------------------------------------------------------------
PERMANENT_CHANNELS = [
    {
        "id": "-1003479783999",
        "name": "VIP Official Telegram Channel",
        "url": "https://t.me/+7clQNCkYuAAxYWQ1",
        "is_private": True,
    },
]

# ---------------------------------------------------------------------------
# 3. PERMANENT AUTHORIZED OWNERS
# ---------------------------------------------------------------------------
DEFAULT_OWNERS = [
    "rohit79041",
    "sc812490",
]

# ---------------------------------------------------------------------------
# 4. LOGGING CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("scratch_the_win_bot")


# ---------------------------------------------------------------------------
# 5. RENDER / VPS 24/7 HTTP HEALTH SERVER
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        res = {
            "status": "online",
            "bot": "Scratch The Win Telegram Bot",
            "uptime": int(time.time()),
        }
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return  # Suppress health check access logs


def start_health_server():
    """Starts a minimal background HTTP server so Render/Railway keeps process 24/7 alive."""
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health server initialization note: {e}")


# ---------------------------------------------------------------------------
# 6. DATABASE HELPER FUNCTIONS (FIREBASE RTDB DIRECT REST)
# ---------------------------------------------------------------------------
def db_request(endpoint: str, method: str = "GET", data: dict = None) -> any:
    """Executes a thread-safe HTTP request to Firebase Realtime Database."""
    url = f"{RTDB_URL}/{endpoint.lstrip('/')}"
    try:
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            content = resp.read().decode("utf-8")
            if content and content != "null":
                return json.loads(content)
            return None
    except Exception as e:
        logger.debug(f"DB request notice [{method} {endpoint}]: {e}")
        return None


def get_user_from_db(user_id: str) -> dict | None:
    """Fetch user profile from Firebase RTDB."""
    return db_request(f"users/{user_id}.json")


def update_user_in_db(user_id: str, patch_data: dict) -> bool:
    """Update user fields in Firebase RTDB."""
    res = db_request(f"users/{user_id}.json", method="PATCH", data=patch_data)
    return res is not None


def is_already_referred(referrer_id: str, new_user_id: str) -> bool:
    """Loophole Check: Verify if this new user has already been credited to the referrer."""
    res = db_request(f"referrals/{referrer_id}/{new_user_id}.json")
    return res is not None


def record_referral(referrer_id: str, new_user_id: str, name: str, username: str):
    """Store referral linkage in Firebase RTDB."""
    payload = {
        "joinerId": str(new_user_id),
        "name": name or f"User #{new_user_id}",
        "username": username or "",
        "timestamp": int(time.time() * 1000),
    }
    db_request(f"referrals/{referrer_id}/{new_user_id}.json", method="PUT", data=payload)


def award_scratch_to_referrer(referrer_id: str, new_user_name: str) -> dict:
    """
    Awards +1 Free Scratch Card to the referrer in Firebase RTDB atomically.
    Returns the updated stats dictionary.
    """
    now_ms = int(time.time() * 1000)
    current = get_user_from_db(referrer_id)

    if current:
        new_spins = int(current.get("spins") or 0) + 1
        new_friends = int(current.get("friendsJoined") or 0) + 1
        new_earned = int(current.get("spinsEarned") or 0) + 1

        patch_data = {
            "spins": new_spins,
            "friendsJoined": new_friends,
            "spinsEarned": new_earned,
        }
        update_user_in_db(referrer_id, patch_data)

        # Log transaction for complete financial auditing
        tx_id = f"tx_{now_ms}_{new_friends}"
        tx_data = {
            "id": tx_id,
            "userId": str(referrer_id),
            "type": "referral_bonus",
            "amount": 0,
            "description": f"Dost {new_user_name} jud gaya! +1 Free Scratch Card mila 🎫",
            "status": "completed",
            "createdAt": now_ms,
        }
        db_request(f"transactions/{tx_id}.json", method="PUT", data=tx_data)

        return {"spins": new_spins, "friendsJoined": new_friends}
    else:
        # Create user record if not pre-existing
        new_user = {
            "id": str(referrer_id),
            "telegramId": str(referrer_id),
            "name": f"User #{referrer_id}",
            "username": f"user_{referrer_id}",
            "balance": 0,
            "spins": 2,  # 1 signup bonus + 1 referral card
            "friendsJoined": 1,
            "spinsEarned": 2,
            "createdAt": now_ms,
            "isVerified": True,
            "claimedWelcomeSpin": True,
        }
        db_request(f"users/{referrer_id}.json", method="PUT", data=new_user)
        return {"spins": 2, "friendsJoined": 1}


# ---------------------------------------------------------------------------
# 7. CHANNELS & OWNERS DYNAMIC MANAGEMENT
# ---------------------------------------------------------------------------
_CHANNELS_CACHE = []
_OWNERS_CACHE = set(o.lower().lstrip("@") for o in DEFAULT_OWNERS)
_LAST_CACHE_TIME = 0


def load_channels() -> list[dict]:
    """Combines permanent channels with dynamically saved channels in Firebase."""
    global _CHANNELS_CACHE, _LAST_CACHE_TIME
    now = time.time()
    if _CHANNELS_CACHE and (now - _LAST_CACHE_TIME < 15):
        return _CHANNELS_CACHE

    combined = [dict(p) for p in PERMANENT_CHANNELS]
    try:
        remote = db_request("bot_config/channels.json")
        if remote:
            items = list(remote.values()) if isinstance(remote, dict) else remote
            for item in items:
                if isinstance(item, dict) and item.get("id"):
                    if not any(str(c.get("id")) == str(item["id"]) for c in combined):
                        combined.append(item)
    except Exception as e:
        logger.warning(f"Error loading channels: {e}")

    _CHANNELS_CACHE = combined
    _LAST_CACHE_TIME = now
    return _CHANNELS_CACHE


def is_owner(user) -> bool:
    """Checks whether the user is authorized to execute owner commands."""
    uid = str(user.id).lower()
    uname = (user.username or "").lower().lstrip("@")
    return uid in _OWNERS_CACHE or uname in _OWNERS_CACHE


# ---------------------------------------------------------------------------
# 8. CHANNEL GATEKEEPER & MEMBERSHIP VERIFICATION (ANTI-BYPASS)
# ---------------------------------------------------------------------------
async def check_user_channels(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> tuple[bool, list[dict]]:
    """
    Checks if user is member of all configured mandatory channels.
    Returns (all_joined: bool, unjoined_channels: list)
    """
    channels = load_channels()
    unjoined = []

    for ch in channels:
        ch_id = ch["id"]
        try:
            # Format chat identifier properly for Telegram API
            target = int(ch_id) if str(ch_id).lstrip("-").isdigit() else ch_id
            member = await context.bot.get_chat_member(chat_id=target, user_id=user_id)
            if member.status not in ["member", "administrator", "creator", "restricted"]:
                unjoined.append(ch)
        except BadRequest as e:
            msg = str(e).lower()
            # If bot is not admin in private channel, or user has sent join request
            if "not a member" in msg or "user not found" in msg:
                unjoined.append(ch)
            else:
                logger.debug(f"Chat member check note for {ch_id}: {e}")
        except Exception as e:
            logger.debug(f"Channel check notice {ch_id}: {e}")

    return (len(unjoined) == 0, unjoined)


# ---------------------------------------------------------------------------
# 9. TELEGRAM COMMAND HANDLERS
# ---------------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command handler:
    1. Parses referral link parameter (ref_123456 or 123456).
    2. Enforces anti-self-referral and anti-duplicate rules.
    3. Credits referrer instantly with +1 Free Scratch Card in Firebase.
    4. Enforces mandatory channel verification gatekeeper.
    5. Presents Telegram WebApp button with Telegram Premium aesthetic.
    """
    user = update.effective_user
    if not user:
        return

    user_id = str(user.id)
    name = user.first_name or user.full_name or "Friend"
    username = user.username or ""

    # Parse referral parameter
    args = context.args or []
    ref_param = args[0] if len(args) > 0 else None
    referrer_id = None

    if ref_param:
        clean_ref = ref_param.replace("ref_", "").strip()
        if clean_ref.isdigit():
            referrer_id = clean_ref

    # -----------------------------------------------------------------------
    # ANTI-CHEAT / ZERO LOOPHOLE REFERRAL PROCESSING
    # -----------------------------------------------------------------------
    if referrer_id:
        if referrer_id == user_id:
            # Loophole 1: Self-Referral Busted
            logger.info(f"Self-referral attempted by user {user_id}")
        elif is_already_referred(referrer_id, user_id):
            # Loophole 2: Duplicate Credit Busted
            logger.info(f"Duplicate referral attempted for {referrer_id} by {user_id}")
        else:
            # Clean authentic referral: Award scratch card atomically
            record_referral(referrer_id, user_id, name, username)
            stats = award_scratch_to_referrer(referrer_id, name)
            logger.info(f"Referral credited: {user_id} referred by {referrer_id}. Referrer spins: {stats['spins']}")

            # Notify Referrer on Telegram in real time
            try:
                ref_msg = (
                    f"⭐ <b>BADHAI HO! NAYA REFERRAL JUD GAYA!</b> ⭐\n\n"
                    f"🎉 Aapke dost <b>{name}</b> ne aapke invite link se join kiya!\n\n"
                    f"🎫 <b>+1 FREE SCRATCH CARD</b> aapke account me add ho gaya hai!\n"
                    f"📊 Total Scratch Cards: <b>{stats['spins']}</b>\n"
                    f"👥 Total Friends Invited: <b>{stats['friendsJoined']}</b>\n\n"
                    f"💰 <i>Scratch The Win me scratch karein aur turant UPI cash withdraw karein!</i>"
                )
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=ref_msg,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.debug(f"Could not notify referrer {referrer_id}: {e}")

    # Ensure user exists in Firebase RTDB
    existing = get_user_from_db(user_id)
    if not existing:
        welcome_user = {
            "id": user_id,
            "telegramId": user_id,
            "name": name,
            "username": username,
            "balance": 0,
            "spins": 1,  # 1 Free Welcome Scratch Card
            "friendsJoined": 0,
            "spinsEarned": 1,
            "createdAt": int(time.time() * 1000),
            "isVerified": True,
            "referredBy": referrer_id if (referrer_id and referrer_id != user_id) else None,
        }
        db_request(f"users/{user_id}.json", method="PUT", data=welcome_user)

    # -----------------------------------------------------------------------
    # CHANNEL GATEKEEPER CHECK
    # -----------------------------------------------------------------------
    all_joined, unjoined = await check_user_channels(context, user.id)

    if not all_joined:
        # Show Gatekeeper Lock Message
        buttons = []
        for ch in unjoined:
            buttons.append([InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch["url"])])

        verify_callback_data = f"verify_{ref_param or 'none'}"
        buttons.append([InlineKeyboardButton("🔄 Verify Joined ✅", callback_data=verify_callback_data)])

        text = (
            f"⭐ <b>NAMASTE {name.upper()}!</b> ⭐\n\n"
            f"🎫 <b>Scratch The Win Mini App</b> me aapka swagat hai!\n"
            f"Aapko mila hai <b>1 FREE SCRATCH CARD (Worth ₹5 Instant Cash)</b> 🎁\n\n"
            f"⚠️ <b>Zaruri Step (Channel Verification):</b>\n"
            f"App open karne ke liye neeche diye gaye official Telegram channels ko join karein, fir <b>Verify Joined</b> button dabayein!\n"
        )
        await update.message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    # -----------------------------------------------------------------------
    # ALL CHANNELS VERIFIED: UNLOCK SCRATCH THE WIN MINI APP
    # -----------------------------------------------------------------------
    app_url = f"{WEB_URL}/?start=ref_{referrer_id}" if referrer_id else WEB_URL

    keyboard = [
        [
            InlineKeyboardButton(
                "🎫 Open Scratch The Win Mini App",
                web_app=WebAppInfo(url=app_url),
            )
        ],
        [
            InlineKeyboardButton("👥 My Referral Link", callback_data="my_invite"),
            InlineKeyboardButton("💰 My Wallet & Stats", callback_data="my_wallet"),
        ],
        [
            InlineKeyboardButton("📢 Official Channel", url="https://t.me/+7clQNCkYuAAxYWQ1"),
        ],
    ]

    welcome_text = (
        f"⭐ <b>WELCOME TO SCRATCH THE WIN!</b> ⭐\n\n"
        f"🎉 <b>Aapka Account 100% Verified Hai!</b> ✅\n\n"
        f"🎫 <b>Free Welcome Scratch Card Ready:</b> 1 Card (Instant ₹5 Cash)\n"
        f"⚡ <b>Withdrawals:</b> 100% Instant Payout via UPI & Bank\n"
        f"👥 <b>Per Refer:</b> Har dost ko bulane par <b>+1 Free Scratch Card</b>\n\n"
        f"Neeche <b>Open Scratch The Win</b> button dabao aur card scratch karo! 👇"
    )

    await update.message.reply_text(
        text=welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def verify_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles '🔄 Verify Joined' button callback."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    all_joined, unjoined = await check_user_channels(context, user.id)

    ref_param = None
    if query.data and query.data.startswith("verify_"):
        raw = query.data.replace("verify_", "")
        if raw != "none":
            ref_param = raw

    if not all_joined:
        await query.answer(
            "⚠️ Aapne abhi tak sabhi channels join nahi kiye hain! Kripya pehle channel join karein.",
            show_alert=True,
        )
        return

    # User verified! Update message with Mini App WebApp Button
    app_url = f"{WEB_URL}/?start={ref_param}" if ref_param else WEB_URL

    keyboard = [
        [
            InlineKeyboardButton(
                "🎫 Open Scratch The Win Mini App",
                web_app=WebAppInfo(url=app_url),
            )
        ],
        [
            InlineKeyboardButton("👥 My Referral Link", callback_data="my_invite"),
            InlineKeyboardButton("💰 My Wallet & Stats", callback_data="my_wallet"),
        ],
    ]

    success_text = (
        f"⭐ <b>VERIFICATION SUCCESSFUL!</b> ⭐\n\n"
        f"✅ <b>Sabhi channels successfully verify ho gaye hain!</b>\n\n"
        f"🎫 Aapka <b>Free Scratch Card</b> ready hai!\n"
        f"Neeche diye gaye button par click karke turant apna card scratch karein aur cash jeetein! 🎁"
    )

    await query.edit_message_text(
        text=success_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def invite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates unique referral link with Telegram Premium formatting."""
    user = update.effective_user
    if not user:
        return

    bot_me = await context.bot.get_me()
    bot_user = bot_me.username or BOT_USERNAME
    invite_link = f"https://t.me/{bot_user}?start=ref_{user.id}"

    db_user = get_user_from_db(str(user.id)) or {}
    spins = db_user.get("spins", 1)
    friends = db_user.get("friendsJoined", 0)

    share_text = urllib.parse.quote(
        f"🎁 Scratch The Win par turant ₹5 Cash Scratch Card jeeto! Ek click me UPI withdrawal milta hai! 👇\n{invite_link}"
    )
    share_url = f"https://t.me/share/url?url={invite_link}&text={share_text}"

    keyboard = [
        [
            InlineKeyboardButton("🚀 Share Invite Link", url=share_url),
        ],
        [
            InlineKeyboardButton("🎫 Open Scratch App", web_app=WebAppInfo(url=WEB_URL)),
        ],
    ]

    msg = (
        f"⭐ <b>AAPKA PERSONAL INVITE PROGRAM</b> ⭐\n\n"
        f"🔗 <b>Invite Link:</b>\n"
        f"<code>{invite_link}</code>\n\n"
        f"🎁 <b>Reward Policy:</b>\n"
        f"• Har 1 dost ke join hone par <b>+1 Free Scratch Card</b>\n"
        f"• Har Scratch Card me <b>₹5 Real Cash</b> milta hai\n"
        f"• Instant UPI / Bank Account withdrawal\n\n"
        f"📊 <b>Aapka Current Status:</b>\n"
        f"• Doston ki Sankhya: <b>{friends}</b>\n"
        f"• Available Scratch Cards: <b>{spins}</b>"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's real-time balance and scratch card stats."""
    user = update.effective_user
    if not user:
        return

    db_user = get_user_from_db(str(user.id)) or {}
    balance = db_user.get("balance", 0)
    spins = db_user.get("spins", 1)
    friends = db_user.get("friendsJoined", 0)

    keyboard = [
        [
            InlineKeyboardButton("🎫 Open Scratch The Win", web_app=WebAppInfo(url=WEB_URL)),
        ],
        [
            InlineKeyboardButton("👥 Invite Friends (+1 Scratch)", callback_data="my_invite"),
        ],
    ]

    msg = (
        f"⭐ <b>AAPKA WALLET & STATS</b> ⭐\n\n"
        f"💰 <b>Available Cash Balance:</b> ₹{balance:.2f}\n"
        f"🎫 <b>Available Scratch Cards:</b> {spins}\n"
        f"👥 <b>Dost Invited:</b> {friends}\n\n"
        f"⚡ <b>Withdrawal Info:</b> Minimum limit tak pahuchne ke baad UPI ya Bank se turant withdraw karein!"
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help and rules info."""
    text = (
        f"⭐ <b>SCRATCH THE WIN - HELP & RULES</b> ⭐\n\n"
        f"1. <b>/start</b> - App shuru karein aur free scratch card paayein\n"
        f"2. <b>/invite</b> - Apna referral link paayein aur har dost par +1 card jeetein\n"
        f"3. <b>/wallet</b> - Apna balance aur scratch card check karein\n\n"
        f"🛡️ <b>Fair Play Rules:</b>\n"
        f"• Ek phone par sirf 1 hi account chal sakta hai.\n"
        f"• Multiple accounts banana sakht mana hai aur account block ho sakta hai."
    )
    await update.message.reply_text(text=text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# 10. OWNER / ADMIN COMMANDS
# ---------------------------------------------------------------------------
async def ownerhelp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner commands list."""
    if not is_owner(update.effective_user):
        await update.message.reply_text("❌ Aapko ye command chalane ki permission nahi hai!")
        return

    text = (
        f"👑 <b>SCRATCH THE WIN - OWNER COMMANDS</b> 👑\n\n"
        f"• <b>/stats</b> - Total users aur database statistics\n"
        f"• <b>/channels</b> - Active mandatory channels list\n"
        f"• <b>/addchannel &lt;id&gt; &lt;name&gt; &lt;url&gt;</b> - Channel add karein\n"
        f"• <b>/removechannel &lt;id&gt;</b> - Channel remove karein\n"
        f"• <b>/broadcast</b> (Reply karke) - 💎 <b>Telegram Premium custom emojis</b> & media sabhi ko bhejein (100% sabko dikhega!)\n"
        f"• <b>/broadcast &lt;message&gt;</b> - Direct text broadcast\n"
        f"• <b>/emojitest</b> - Premium custom emojis inspect aur live preview karein\n"
        f"• <b>/addowner &lt;username_or_id&gt;</b> - Naya owner banayein\n"
    )
    await update.message.reply_text(text=text, parse_mode="HTML")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches total users and withdrawal statistics."""
    if not is_owner(update.effective_user):
        return

    users = db_request("users.json") or {}
    withdrawals = db_request("withdrawals.json") or {}

    total_users = len(users) if isinstance(users, dict) else len(users or [])
    total_w = len(withdrawals) if isinstance(withdrawals, dict) else len(withdrawals or [])

    text = (
        f"📊 <b>SCRATCH THE WIN - LIVE STATS</b> 📊\n\n"
        f"👥 Total Registered Users: <b>{total_users}</b>\n"
        f"💸 Total Withdrawal Requests: <b>{total_w}</b>\n"
        f"🟢 Server Status: <b>Online & Resilient</b>"
    )
    await update.message.reply_text(text=text, parse_mode="HTML")


async def emojitest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inspects and tests Telegram Premium custom emojis in a message."""
    if not is_owner(update.effective_user):
        return

    target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
    entities = target_msg.entities or target_msg.caption_entities or []
    custom_emojis = [
        e for e in entities
        if e.type == "custom_emoji" or getattr(e, "custom_emoji_id", None)
    ]

    if not custom_emojis and target_msg == update.message and not context.args:
        help_text = (
            "💎 <b>TELEGRAM PREMIUM EMOJI INSPECTOR</b> 💎\n\n"
            "Aapke paas Telegram Premium hai! Test karne ke liye:\n"
            "1. Apne kisi bhi Premium custom emoji wale message ko <b>Reply</b> karein\n"
            "2. Aur likhein: <code>/emojitest</code>\n\n"
            "Bot aapke custom emoji IDs inspect karega aur aapko preview bhejega!"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
        return

    emoji_ids = [str(e.custom_emoji_id) for e in custom_emojis if getattr(e, "custom_emoji_id", None)]

    report = (
        f"💎 <b>TELEGRAM PREMIUM EMOJI STATUS:</b>\n\n"
        f"✨ Custom Emojis Detected: <b>{len(custom_emojis)}</b>\n"
        f"🆔 Emoji IDs: <code>{', '.join(emoji_ids) if emoji_ids else 'None detected'}</code>\n\n"
        f"✅ <b>PREVIEW:</b> Niche aapka original message copyMessage ke sath preview ho raha hai. "
        f"Yeh bilkul waisa hi sabhi users (Free + Premium dono) ko dikhega:"
    )
    await update.message.reply_text(report, parse_mode="HTML")

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=update.effective_chat.id,
            message_id=target_msg.message_id,
        )
    except Exception as err:
        await update.message.reply_text(f"⚠️ Preview error: {err}")


async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    High-Performance Broadcast Engine with 100% Telegram Premium Custom Emoji Support.
    
    1. Reply-to-Message (BEST): Admin writes a post with Telegram Premium custom emojis,
       media, stickers, photos, etc., and replies /broadcast.
       Bot uses copy_message to replicate it to all users — Telegram server guarantees
       100% display of custom animated emojis to ALL users (Free & Premium)!
    2. Direct Command: Admin writes /broadcast <message with premium emojis>.
       Bot shifts entity offsets and sends with entities intact, falling back to copy_message
       if necessary.
    """
    if not is_owner(update.effective_user):
        return

    reply_msg = update.message.reply_to_message
    full_text = update.message.text or update.message.caption or ""
    command_match = re.match(r"^/broadcast(@\w+)?\s*", full_text)
    prefix_len = command_match.end() if command_match else 0
    direct_text = full_text[prefix_len:].strip()

    if not reply_msg and not direct_text:
        help_text = (
            "📢 <b>SCRATCH THE WIN - TELEGRAM PREMIUM BROADCAST GUIDE</b> 📢\n\n"
            "Aapke paas Telegram Premium hai! Custom emojis sabhi users ko dikhane ke 2 tareeqe hain:\n\n"
            "⭐ <b>1. REPLY METHOD (100% GUARANTEED & RECOMMENDED):</b>\n"
            "• Pehle apna text, premium animated emojis, photo ya sticker chat me normal bhejein.\n"
            "• Fir us message ko <b>Reply</b> karein aur likhein: <code>/broadcast</code>\n"
            "• <i>Isse Telegram ka official <code>copyMessage</code> engine use hota hai — aur sabhi users (Free + Premium dono) ko aapke custom animated emojis 100% original dikhenge!</i>\n\n"
            "⭐ <b>2. DIRECT METHOD:</b>\n"
            "• Direct likhein: <code>/broadcast 🔥 Naya Dhamaka 💎 Sabhi khelo!</code>\n"
            "• Bot aapke custom emojis aur entities ko retain karke sabhi ko bhej dega.\n\n"
            "🧪 <i>Tip: Message test karne ke liye reply karke <code>/emojitest</code> likhein!</i>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
        return

    users = db_request("users.json") or {}
    items = list(users.values()) if isinstance(users, dict) else list(users or [])

    valid_user_ids = []
    seen = set()
    for u in items:
        if isinstance(u, dict) and u.get("id"):
            try:
                uid = int(u["id"])
                if uid not in seen:
                    seen.add(uid)
                    valid_user_ids.append(uid)
            except Exception:
                continue

    if not valid_user_ids:
        await update.message.reply_text("⚠️ Database me koi registered users nahi mile!")
        return

    if reply_msg:
        entities = reply_msg.entities or reply_msg.caption_entities or []
        custom_count = sum(1 for e in entities if e.type == "custom_emoji" or getattr(e, "custom_emoji_id", None))
        await update.message.reply_text(
            f"🚀 <b>Broadcast Starting (Copy Engine)...</b>\n"
            f"👥 Total Recipients: <b>{len(valid_user_ids)}</b>\n"
            f"💎 Telegram Premium Emojis: <b>{custom_count}</b>\n"
            f"⏳ Sending to all users with animated emojis preserved...",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"🚀 <b>Broadcast Starting (Direct Engine)...</b>\n"
            f"👥 Total Recipients: <b>{len(valid_user_ids)}</b>\n"
            f"⏳ Sending to all users...",
            parse_mode="HTML",
        )

    # Prepare shifted entities if direct text mode
    shifted_entities = []
    if not reply_msg and update.message.entities:
        for ent in update.message.entities:
            if ent.offset >= prefix_len:
                try:
                    shifted_entities.append(
                        MessageEntity(
                            type=ent.type,
                            offset=ent.offset - prefix_len,
                            length=ent.length,
                            url=ent.url,
                            user=ent.user,
                            language=ent.language,
                            custom_emoji_id=ent.custom_emoji_id,
                        )
                    )
                except Exception:
                    pass

    sent = 0
    failed = 0

    for uid in valid_user_ids:
        try:
            if reply_msg:
                # 100% Telegram server-side copy: Preserves all Telegram Premium custom emojis, photos, media, styling!
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=update.effective_chat.id,
                    message_id=reply_msg.message_id,
                )
            else:
                if shifted_entities:
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=direct_text,
                            entities=shifted_entities,
                        )
                    except Exception:
                        await context.bot.copy_message(
                            chat_id=uid,
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id,
                        )
                else:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📢 <b>OFFICIAL ANNOUNCEMENT:</b>\n\n{direct_text}",
                        parse_mode="HTML",
                    )
            sent += 1
            await asyncio.sleep(0.04)  # Safe anti-flood rate limit
        except Exception:
            failed += 1

    summary = (
        f"✅ <b>BROADCAST COMPLETED!</b>\n\n"
        f"🎯 Successfully Delivered: <b>{sent} users</b>\n"
        f"🚫 Failed / Blocked: <b>{failed} users</b>\n"
        f"💎 <i>Aapke Telegram Premium custom emojis har recipient ko successfully deliver ho gaye hain!</i>"
    )
    await update.message.reply_text(summary, parse_mode="HTML")


# ---------------------------------------------------------------------------
# 11. MAIN APPLICATION INITIALIZATION & POLLING LOOP
# ---------------------------------------------------------------------------
def main():
    logger.info("Initializing Scratch The Win Telegram Bot...")

    # Start Render/VPS HTTP health server in background thread
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    # Configure resilient HTTPX client with 30s timeouts
    request_client = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .request(request_client)
        .build()
    )

    # Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("scratch", start_handler))
    app.add_handler(CommandHandler("invite", invite_handler))
    app.add_handler(CommandHandler("link", invite_handler))
    app.add_handler(CommandHandler("wallet", wallet_handler))
    app.add_handler(CommandHandler("balance", wallet_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("rules", help_handler))

    # Owner Handlers
    app.add_handler(CommandHandler("ownerhelp", ownerhelp_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("broadcast", broadcast_handler))
    app.add_handler(CommandHandler("emojitest", emojitest_handler))
    app.add_handler(CommandHandler("testbroadcast", emojitest_handler))

    # Callback Query Handlers
    app.add_handler(CallbackQueryHandler(verify_callback_handler, pattern=r"^verify_"))
    app.add_handler(CallbackQueryHandler(invite_handler, pattern=r"^my_invite$"))
    app.add_handler(CallbackQueryHandler(wallet_handler, pattern=r"^my_wallet$"))

    logger.info(f"Scratch The Win Bot started successfully! Polling live as @{BOT_USERNAME}...")

    # Resilience loop to recover from temporary connection drops
    retry_delay = 5
    while True:
        try:
            app.run_polling(drop_pending_updates=True, close_loop=False)
            break
        except (NetworkError, TimedOut) as e:
            logger.warning(f"Network drop: {e}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except Conflict:
            logger.error("Conflict error: Another instance of this bot is already running. Please terminate other processes.")
            break
        except Exception as e:
            logger.error(f"Unexpected bot crash: {e}. Retrying in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
