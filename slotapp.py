
from flask import Flask, render_template_string, request, jsonify, session, redirect, send_from_directory
import random, string, json, os, requests, base64
from io import BytesIO
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

app = Flask(__name__)
app.secret_key = 'gag2026_secret_key'

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "jalwa123"
DEFAULT_MAIN_API_KEY = "your_secret_api_key_2026_xyz"
AURA_API_KEY = "aura_e8b9c915fb7a628b2010ee0f3e2ffd70426fba35"
AURA_BASE_URL = "https://node1.aurax.sbs/api/v1/exec"
AURA_WAVE_ACCOUNT = "09691835083"
AURA_HEADERS = {"Authorization": f"Bearer {AURA_API_KEY}", "Content-Type": "application/json"}

DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
USERS_FILE          = os.path.join(DATA_DIR, 'users.json')
DEPOSITS_FILE       = os.path.join(DATA_DIR, 'deposits.json')
WITHDRAWALS_FILE    = os.path.join(DATA_DIR, 'withdrawals.json')
BETS_FILE           = os.path.join(DATA_DIR, 'bets.json')
NOTIFICATIONS_FILE  = os.path.join(DATA_DIR, 'notifications.json')
BONUS_CODES_FILE    = os.path.join(DATA_DIR, 'bonus_codes.json')
SLIDERS_FILE        = os.path.join(DATA_DIR, 'sliders.json')
SETTINGS_FILE       = os.path.join(DATA_DIR, 'settings.json')
GAME_HISTORY_FILE   = os.path.join(DATA_DIR, 'game_history.json')
BONUS_LOGS_FILE     = os.path.join(DATA_DIR, 'bonus_logs.json')
FORCED_RESULTS_FILE = os.path.join(DATA_DIR, 'forced_results.json')
DEMO_GAMES_FILE     = os.path.join(DATA_DIR, 'demo_games.json')
ADMIN_CRED_FILE     = os.path.join(DATA_DIR, 'admin_cred.json')
API_LOG_FILE        = os.path.join(DATA_DIR, 'api_logs.json')
AFRICAN_BUFFALO_HISTORY_FILE = os.path.join(DATA_DIR, 'african_buffalo_history.json')
DAILY_REFUNDS_FILE = os.path.join(DATA_DIR, 'daily_refunds.json')

# ============================================================
# LOAD 128 GAMES from gag_games.py
# ============================================================
try:
    from gag_games import DEFAULT_GAMES, TOTAL_GAMES
    print(f"[LOADED] {TOTAL_GAMES} demo games from gag_games.py")
except ImportError:
    print("[WARNING] gag_games.py not found. Please create it first!")
    DEFAULT_GAMES = {'Pragmatic': []}

from african_buffalo_host import balance as african_buffalo_balance
from african_buffalo_host import credit_win as african_buffalo_credit_win
from african_buffalo_host import debit_playable as african_buffalo_debit_playable
from african_buffalo_host import playable_balance as african_buffalo_playable_balance
from african_buffalo_host import rtp_for_user as african_buffalo_rtp_for_user
from african_buffalo_host import spin_result as african_buffalo_spin_result
from african_buffalo_host import view_result as african_buffalo_view_result

AFRICAN_BUFFALO_DIR = os.path.join(os.path.dirname(__file__), 'african_buffalo')
AFRICAN_BUFFALO_GAME = {
    'title': 'African Buffalo',
    'img': '/african-buffalo/demo_images/african_buffalo.png',
    'url': '/african-buffalo/',
    'badge': 'new',
    'internal': True,
}
AFRICAN_BUFFALO_ROOMS = [
    {'room_id': 1, 'title': 'African Buffalo · Room 1'},
    {'room_id': 2, 'title': 'African Buffalo · Room 2'},
    {'room_id': 3, 'title': 'African Buffalo · Room 3'},
    {'room_id': 4, 'title': 'African Buffalo · Room 4'},
]

# ============================================================
# HELPERS
# ============================================================
def load_json(fp, default=None):
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default if default is not None else []
    return default if default is not None else []

def save_json(fp, data):
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def remove_uniform_background(data_url):
    """Remove a contiguous, near-uniform border background and return a PNG data URL.

    This deliberately removes only pixels connected to the image edges, preserving
    interior colors and avoiding destructive subject-wide color replacement.
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError('Pillow is required for background removal. Install with: python -m pip install pillow')
    raw = str(data_url or '')
    if ',' not in raw:
        raise ValueError('Invalid image data')
    blob = base64.b64decode(raw.split(',', 1)[1])
    image = Image.open(BytesIO(blob)).convert('RGBA')
    if image.width * image.height > 12_000_000:
        raise ValueError('Image is too large')
    px = image.load(); w, h = image.size
    samples = [px[x, y][:3] for x, y in [(0,0), (w-1,0), (0,h-1), (w-1,h-1)]]
    bg = tuple(sum(v[i] for v in samples)//len(samples) for i in range(3))
    tolerance = 34
    seen = bytearray(w*h); stack = [(x,y) for x,y in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]]
    while stack:
        x,y = stack.pop(); idx=y*w+x
        if seen[idx]: continue
        r,g,b,a = px[x,y]
        if max(abs(r-bg[0]), abs(g-bg[1]), abs(b-bg[2])) > tolerance: continue
        seen[idx]=1; px[x,y]=(r,g,b,0)
        if x: stack.append((x-1,y))
        if x<w-1: stack.append((x+1,y))
        if y: stack.append((x,y-1))
        if y<h-1: stack.append((x,y+1))
    out=BytesIO(); image.save(out, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')

def local_now():
    if ZoneInfo:
        try:
            return datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Yangon'))
        except Exception:
            pass
    # Termux may not ship the IANA tzdata package. Myanmar has a fixed UTC+06:30 offset.
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=6, minutes=30)))

def wallet_total(user):
    wallet = user.setdefault('wallet', {})
    return int(wallet.get('deposit', 0) or 0) + int(wallet.get('winning', 0) or 0)

def turnover_status(user):
    return {
        'deposit_wagered': int(user.get('depositWagered', 0) or 0),
        'deposit_required': int(user.get('depositWagerRequired', 0) or 0),
        'bonus_wagered': int(user.get('bonusWagered', 0) or 0),
        'bonus_required': int(user.get('bonusWagerRequired', 0) or 0),
    }

def record_turnover(user, amount, game='unknown'):
    amount = max(0, int(amount or 0))
    if amount:
        user['depositWagered'] = int(user.get('depositWagered', 0) or 0) + amount
        if int(user.get('bonusWagerRequired', 0) or 0) > 0:
            user['bonusWagered'] = int(user.get('bonusWagered', 0) or 0) + amount
        user['lastWagerGame'] = game
        user['lastWagerAt'] = datetime.now().isoformat()

def can_open_wallet_action(user):
    status = turnover_status(user)
    if status['deposit_required'] and status['deposit_wagered'] < status['deposit_required']:
        return False, f"Deposit turnover required: {status['deposit_required']:,} Ks; completed {status['deposit_wagered']:,} Ks"
    if status['bonus_required'] and status['bonus_wagered'] < status['bonus_required']:
        return False, f"Bonus turnover required: {status['bonus_required']:,} Ks; completed {status['bonus_wagered']:,} Ks"
    return True, ''

def run_daily_lossback():
    now = local_now()
    if (now.hour, now.minute) < (14, 30):
        return
    settings = get_settings()
    day = now.date().isoformat()
    if settings.get('daily_lossback_last_run') == day:
        return
    deposits = load_json(DEPOSITS_FILE, [])
    users = load_json(USERS_FILE, [])
    refunds = load_json(DAILY_REFUNDS_FILE, [])
    for user in users:
        approved = [d for d in deposits if d.get('uid') == user.get('uid') and d.get('status') == 'success'
                    and str(d.get('approved_at') or d.get('date', ''))[:10] == day]
        if not approved or any(r.get('uid') == user.get('uid') and r.get('date') == day for r in refunds):
            continue
        total_deposit = sum(int(d.get('amount', 0) or 0) for d in approved)
        opening = int(approved[0].get('balance_before', 0) or 0)
        loss = max(0, total_deposit + opening - wallet_total(user))
        refund = int(loss * 0.10)
        if refund:
            user.setdefault('wallet', {})['winning'] = int(user['wallet'].get('winning', 0) or 0) + refund
        refunds.append({'uid': user.get('uid'), 'date': day, 'deposited': total_deposit,
                        'loss': loss, 'refund': refund, 'timestamp': datetime.now().isoformat()})
        update_user(user.get('uid'), user)
    save_json(DAILY_REFUNDS_FILE, refunds[-10000:])
    settings['daily_lossback_last_run'] = day
    save_json(SETTINGS_FILE, settings)

@app.before_request
def daily_lossback_hook():
    run_daily_lossback()

def get_admin_creds():
    c = load_json(ADMIN_CRED_FILE, None)
    if not c or not isinstance(c, dict):
        c = {'username': DEFAULT_ADMIN_USERNAME, 'password': DEFAULT_ADMIN_PASSWORD}
        save_json(ADMIN_CRED_FILE, c)
    return c

def get_main_api_key():
    s = load_json(SETTINGS_FILE, {})
    return s.get('main_api_key', DEFAULT_MAIN_API_KEY)

def get_demo_games():
    games = load_json(DEMO_GAMES_FILE, None)
    if not games or not isinstance(games, dict) or len(games) == 0:
        games = DEFAULT_GAMES
        save_json(DEMO_GAMES_FILE, games)
    # Keep four local Buffalo rooms between the existing catalogue and Wingo area.
    rooms = []
    for room in AFRICAN_BUFFALO_ROOMS:
        card = dict(AFRICAN_BUFFALO_GAME)
        card.update(room)
        card['img'] = AFRICAN_BUFFALO_GAME['img']
        card['url'] = AFRICAN_BUFFALO_GAME['url']
        card['internal'] = 'buffalo_room'
        rooms.append(card)
    if games.get('African Buffalo') != rooms:
        games['African Buffalo'] = rooms
        save_json(DEMO_GAMES_FILE, games)
    return games

def generate_uid():
    while True:
        uid = ''.join(random.choices(string.digits, k=6))
        if not get_user_by_uid(uid):
            return uid

def get_user_by_uid(uid):
    for u in load_json(USERS_FILE, []):
        if u.get('uid') == uid:
            return u
    return None

def get_user_by_contact(contact):
    contact_str = str(contact).strip()
    for u in load_json(USERS_FILE, []):
        if str(u.get('contact', '')).strip() == contact_str:
            return u
    return None

def update_user(uid, data):
    users = load_json(USERS_FILE, [])
    for i, u in enumerate(users):
        if u.get('uid') == uid:
            users[i].update(data)
            save_json(USERS_FILE, users)
            return True
    return False

def promote_bonus_to_real(u):
    """Move the user's bonus wallet into playable winning funds once unlocked."""
    wallet = u.setdefault('wallet', {})
    bonus = int(wallet.get('bonus', 0) or 0)
    if bonus > 0:
        wallet['bonus'] = 0
        wallet['winning'] = int(wallet.get('winning', 0) or 0) + bonus
    return bonus

def get_settings():
    s = load_json(SETTINGS_FILE, {})
    return s if isinstance(s, dict) else {}

def number_to_color(n):
    if n in [2, 4, 6, 8]: return 'red'
    if n in [1, 3, 7, 9]: return 'green'
    if n == 0: return 'red-v'
    if n == 5: return 'green-v'
    return 'green'

def hash_result(period_id, duration):
    combined = period_id + "_" + str(duration)
    seed = 0
    for c in combined:
        seed = (seed ^ ord(c)) * 0x5bd1e995
        seed = seed ^ (seed >> 15)
    t = (seed + 0x6D2B79F5) & 0xFFFFFFFF
    t = ((t ^ (t >> 15)) * 0x5bd1e995) & 0xFFFFFFFF
    t = (t ^ (t >> 13)) & 0xFFFFFFFF
    t = (t * 0x5bd1e995) & 0xFFFFFFFF
    t = (t ^ (t >> 16)) & 0xFFFFFFFF
    return int((t / 4294967296) * 10)

def generate_result(period_id, duration):
    forced = load_json(FORCED_RESULTS_FILE, [])
    for f in forced:
        if f.get('duration') == duration and not f.get('used'):
            n = f.get('number')
            f['used'] = True
            save_json(FORCED_RESULTS_FILE, forced)
            return {'period': period_id, 'number': n,
                    'size': 'Big' if n >= 5 else 'Small',
                    'color': number_to_color(n)}
    n = hash_result(period_id, duration)
    return {'period': period_id, 'number': n,
            'size': 'Big' if n >= 5 else 'Small',
            'color': number_to_color(n)}

def log_api_request(endpoint, uid, data, ip):
    logs = load_json(API_LOG_FILE, [])
    logs.append({'endpoint': endpoint, 'uid': uid, 'data': data, 'ip': ip,
                 'timestamp': datetime.now().isoformat()})
    save_json(API_LOG_FILE, logs[-500:])

def verify_wave_payment(digits):
    try:
        payload = {"cmd": "verify_direct", "provider": "wave",
                   "account": AURA_WAVE_ACCOUNT, "digits": str(digits)}
        r = requests.post(AURA_BASE_URL, headers=AURA_HEADERS, json=payload, timeout=30)
        res = r.json()
        if not res.get("success"):
            return False, None, res.get("message", "verify_failed")
        return True, res.get("data", {}), "matched"
    except requests.exceptions.Timeout:
        return False, None, "timeout"
    except Exception as e:
        return False, None, f"error: {str(e)}"

def get_wave_balance():
    try:
        r = requests.post(AURA_BASE_URL, headers=AURA_HEADERS,
                          json={"cmd": "balance", "provider": "wave",
                                "account": AURA_WAVE_ACCOUNT}, timeout=20)
        return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

# ============================================================
# USER HTML — GAG2026 STYLE
# ============================================================
USER_HTML = r'''<!DOCTYPE html>
<html lang="my">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<title>GAG2026 - gag game site</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Padauk:wght@400;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root{
  --gold:#FFD700;
  --gold-2:#FFA500;
  --gold-dark:#B8860B;
  --purple:#9D4EDD;
  --purple-dark:#5A189A;
  --purple-light:#C77DFF;
  --cyan:#00E5FF;
  --cyan-glow:rgba(0,229,255,0.6);
  --green:#28c76f;
  --red:#ea5455;
  --bg-dark:#050208;
  --card-glass:rgba(20,10,35,0.75);
  --border-glass:rgba(157,78,221,0.3);
  --safe-bottom:env(safe-area-inset-bottom, 0px);
  --safe-top:env(safe-area-inset-top, 0px);
  --page-bg-img:none;
}

*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins','Padauk',sans-serif;-webkit-tap-highlight-color:transparent;}
html{-webkit-text-size-adjust:100%;}
html,body{width:100%;height:100%;overflow-x:hidden;}

body{
  background:var(--bg-dark);
  color:#fff;
  display:flex;justify-content:center;align-items:flex-start;
  min-height:100vh;min-height:100dvh;
  overflow-x:hidden;
  background-image:var(--page-bg-img);
  background-size:cover;
  background-position:center;
  background-attachment:fixed;
  background-repeat:no-repeat;
}
body::before{
  content:'';
  position:fixed;top:0;left:0;width:100%;height:100%;
  background:radial-gradient(ellipse at top, rgba(157,78,221,0.15), transparent 60%),
             radial-gradient(ellipse at bottom, rgba(0,229,255,0.08), transparent 60%),
             rgba(0,0,0,0.6);
  z-index:-1;
  display:none;
}
body.has-bg::before{display:block;}

.app-container{width:100%;max-width:480px;min-height:100vh;min-height:100dvh;position:relative;margin:0 auto;overflow-x:hidden;}

/* Professional light/dark theme tokens. The default remains dark; the toggle persists per browser. */
body[data-theme="light"]{--bg-dark:#f4f6f8;--card-glass:rgba(255,255,255,.94);--border-glass:rgba(15,23,42,.12);color:#172033;background-color:#f4f6f8;}
body[data-theme="light"]::before{display:none;}
body[data-theme="light"] header{background:rgba(255,255,255,.96);border-bottom-color:rgba(15,23,42,.10);box-shadow:0 3px 16px rgba(15,23,42,.08);}
body[data-theme="light"] .user-greeting,body[data-theme="light"] .section-title,body[data-theme="light"] .wallet-bal-label{background:none;-webkit-text-fill-color:initial;color:#172033;}
body[data-theme="light"] .sidebar{background:#fff;border-right-color:rgba(15,23,42,.10);}
body[data-theme="light"] .sidebar-header-section{background:#f7f8fa;border-bottom-color:rgba(15,23,42,.10);}
body[data-theme="light"] .sidebar-menu li{color:#64748b;}
body[data-theme="light"] .sidebar-menu li:hover,body[data-theme="light"] .sidebar-menu li.active{background:#eef2f7;color:#172033;border-left-color:#334155;}
body[data-theme="light"] .stat-box,body[data-theme="light"] .leaderboard-section,body[data-theme="light"] .wallet-card,body[data-theme="light"] .game-card,body[data-theme="light"] .refer-card,body[data-theme="light"] .bonus-card,body[data-theme="light"] .history-card{background:#fff;border-color:rgba(15,23,42,.10);box-shadow:0 8px 24px rgba(15,23,42,.06);}
body[data-theme="light"] .section-title{border-left-color:#475569;}
body[data-theme="light"] .section-title i,body[data-theme="light"] .bell-icon{color:#475569;}
body[data-theme="light"] .muted,body[data-theme="light"] .sub,body[data-theme="light"] .hint{color:#64748b;}
body[data-theme="light"] input,body[data-theme="light"] select,body[data-theme="light"] textarea{background:#fff;color:#172033;border-color:rgba(15,23,42,.14);}
.theme-toggle{width:38px;height:34px;margin:0;padding:0;border:1px solid rgba(148,163,184,.35);border-radius:10px;background:rgba(255,255,255,.08);color:var(--gold);display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:none;}
body[data-theme="light"] .theme-toggle{background:#f1f5f9;color:#334155;border-color:#cbd5e1;}

/* ====== LOADING OVERLAY (Cyan) ====== */
#loading-overlay{
  position:fixed;top:0;left:0;width:100%;height:100%;
  background:rgba(5,2,8,0.96);
  z-index:99999;
  display:none;
  justify-content:center;align-items:center;flex-direction:column;
  gap:28px;
}
#loading-overlay.active{display:flex;}
.cyan-spinner{
  position:relative;
  width:90px;height:90px;
}
.cyan-spinner .dot{
  position:absolute;
  top:50%;left:50%;
  width:100%;height:100%;
  margin-left:-50%;margin-top:-50%;
  border-radius:50%;
  animation:cyanSpin 1.6s linear infinite;
}
.cyan-spinner .dot::before{
  content:'';
  position:absolute;
  top:0;left:50%;
  transform:translateX(-50%);
  width:10px;height:10px;
  background:var(--cyan);
  border-radius:50%;
  box-shadow:0 0 15px var(--cyan), 0 0 30px var(--cyan), 0 0 45px var(--cyan-glow);
}
.cyan-spinner .dot:nth-child(1){animation-delay:0s;}
.cyan-spinner .dot:nth-child(2){animation-delay:-0.13s;}
.cyan-spinner .dot:nth-child(3){animation-delay:-0.26s;}
.cyan-spinner .dot:nth-child(4){animation-delay:-0.39s;}
.cyan-spinner .dot:nth-child(5){animation-delay:-0.52s;}
.cyan-spinner .dot:nth-child(6){animation-delay:-0.65s;}
.cyan-spinner .dot:nth-child(7){animation-delay:-0.78s;}
.cyan-spinner .dot:nth-child(8){animation-delay:-0.91s;}
.cyan-spinner .dot:nth-child(9){animation-delay:-1.04s;}
.cyan-spinner .dot:nth-child(10){animation-delay:-1.17s;}
.cyan-spinner .dot:nth-child(11){animation-delay:-1.30s;}
.cyan-spinner .dot:nth-child(12){animation-delay:-1.43s;}
@keyframes cyanSpin{to{transform:rotate(360deg);}}
.loading-text{
  color:var(--cyan);
  font-family:'Orbitron',sans-serif;
  font-size:26px;font-weight:900;letter-spacing:6px;
  text-shadow:0 0 10px var(--cyan), 0 0 25px var(--cyan-glow), 0 0 40px var(--cyan-glow);
  animation:loadingPulse 1.5s ease-in-out infinite;
}
@keyframes loadingPulse{
  0%,100%{opacity:1;transform:scale(1);}
  50%{opacity:0.6;transform:scale(1.05);}
}

/* ====== AUTH ====== */
#auth-section{
  position:fixed;top:0;left:0;width:100%;height:100%;
  min-height:100vh;min-height:100dvh;
  background-size:cover;background-position:center;
  z-index:5000;padding:20px;
  padding-top:calc(20px + var(--safe-top));
  display:flex;flex-direction:column;justify-content:center;align-items:center;
  overflow-y:auto;-webkit-overflow-scrolling:touch;
}
#auth-section::before{
  content:'';position:absolute;top:0;left:0;width:100%;height:100%;
  background:linear-gradient(135deg, rgba(90,24,154,0.85), rgba(5,2,8,0.95));
  z-index:-1;
}
.auth-container{width:100%;max-width:420px;position:relative;z-index:2;margin:auto 0;}
.auth-logo-top{display:flex;align-items:center;gap:12px;margin-bottom:20px;justify-content:center;flex-direction:column;}
.auth-logo-top img{
  max-width:280px;width:100%;height:auto;object-fit:contain;
  filter:drop-shadow(0 6px 20px rgba(255,215,0,0.5));
}
.auth-logo-top span{
  font-family:'Orbitron',sans-serif;
  font-size:20px;font-weight:900;
  background:linear-gradient(180deg,#FFD700 30%,#FFA500 70%,#B8860B 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  letter-spacing:1.5px;
  filter:drop-shadow(0 2px 8px rgba(157,78,221,0.6));
}
.auth-card{
  background:var(--card-glass);
  border:1px solid var(--border-glass);
  border-radius:22px;
  padding:32px 26px;
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  box-shadow:0 20px 60px rgba(90,24,154,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
  position:relative;overflow:hidden;
}
.auth-card::before{
  content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;
  background:radial-gradient(circle, rgba(157,78,221,0.15), transparent 70%);
  animation:authGlow 8s ease-in-out infinite;
  pointer-events:none;
}
@keyframes authGlow{
  0%,100%{transform:translate(0,0);}
  50%{transform:translate(20px,20px);}
}
.auth-subtitle{color:var(--gold);font-size:11px;letter-spacing:3px;font-weight:700;text-transform:uppercase;margin-bottom:8px;position:relative;z-index:1;}
.auth-title{font-size:24px;font-weight:800;color:#fff;margin-bottom:8px;line-height:1.3;position:relative;z-index:1;}
.auth-desc{color:#a8a4b8;font-size:13px;margin-bottom:25px;position:relative;z-index:1;}
.auth-input-group{margin-bottom:18px;position:relative;z-index:1;}
.auth-input-group label{font-size:13px;color:#c5b8e0;margin-bottom:8px;display:block;font-weight:500;}
.input-wrapper{
  position:relative;display:flex;align-items:center;
  background:rgba(15,5,30,0.8);
  border:1px solid rgba(157,78,221,0.3);
  border-radius:14px;overflow:hidden;transition:0.3s;
}
.input-wrapper:focus-within{
  border-color:var(--gold);
  box-shadow:0 0 0 3px rgba(255,215,0,0.15), 0 0 20px rgba(157,78,221,0.3);
}
.input-prefix{
  padding:14px 12px;
  background:linear-gradient(135deg, rgba(157,78,221,0.3), rgba(90,24,154,0.4));
  color:#fff;font-size:14px;
  display:flex;align-items:center;gap:6px;
  border-right:1px solid rgba(157,78,221,0.3);
  white-space:nowrap;font-weight:700;
}
.auth-input{flex:1;padding:14px 15px;background:transparent;border:none;color:#fff;outline:none;font-size:14px;width:100%;min-width:0;}
.auth-input::placeholder{color:#5a4a75;}
.toggle-pass{position:absolute;right:15px;top:50%;transform:translateY(-50%);cursor:pointer;color:#7a6b95;font-size:15px;z-index:5;padding:5px;}
.auth-checkbox{display:flex;align-items:flex-start;gap:10px;margin:20px 0;position:relative;z-index:1;}
.auth-checkbox input{margin-top:3px;width:18px;height:18px;accent-color:var(--gold);cursor:pointer;flex-shrink:0;}
.auth-checkbox label{font-size:12px;color:#a8a4b8;line-height:1.5;cursor:pointer;}
.auth-btn{
  width:100%;padding:16px;
  background:linear-gradient(135deg,#FFD700 0%,#FFA500 50%,#B8860B 100%);
  border:none;border-radius:14px;color:#1a0a2e;
  font-weight:900;font-size:16px;cursor:pointer;
  position:relative;z-index:1;
  box-shadow:0 8px 25px rgba(255,165,0,0.4), inset 0 1px 0 rgba(255,255,255,0.4);
  transition:0.3s;
}
.auth-btn:active{transform:scale(0.98);}
.auth-btn:disabled{opacity:0.6;cursor:not-allowed;}
.auth-link{text-align:center;margin-top:20px;font-size:13px;color:#a8a4b8;position:relative;z-index:1;}
.auth-link span{color:var(--gold);cursor:pointer;font-weight:700;}
.auth-error{
  background:rgba(239,68,68,0.15);
  border:1px solid rgba(239,68,68,0.4);
  color:#fca5a5;padding:12px 15px;border-radius:12px;
  font-size:13px;margin-bottom:18px;display:none;line-height:1.5;
  position:relative;z-index:1;
}
.auth-error.show{display:block;animation:shake 0.4s;}
.auth-error i{margin-right:8px;}
@keyframes shake{0%,100%{transform:translateX(0);}25%{transform:translateX(-6px);}75%{transform:translateX(6px);}}

/* ====== APP ====== */
#app-content{display:none;width:100%;max-width:480px;position:relative;min-height:100vh;min-height:100dvh;padding-bottom:calc(80px + var(--safe-bottom));}

header{
  display:flex;justify-content:space-between;align-items:center;
  padding:12px 15px;
  background:linear-gradient(90deg, rgba(90,24,154,0.9), rgba(40,10,70,0.95));
  backdrop-filter:blur(15px);-webkit-backdrop-filter:blur(15px);
  position:sticky;top:0;z-index:50;
  border-bottom:1px solid rgba(255,215,0,0.2);
  box-shadow:0 4px 20px rgba(90,24,154,0.4);
}
.header-left{display:flex;align-items:center;gap:15px;flex:1;min-width:0;}
.menu-btn{
  font-size:22px;color:var(--gold);cursor:pointer;flex-shrink:0;
  width:38px;height:38px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  background:rgba(157,78,221,0.2);
  transition:0.3s;
}
.menu-btn:active{transform:scale(0.9);}
.user-greeting{
  font-size:15px;font-weight:700;
  background:linear-gradient(180deg,#FFD700,#FFA500);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.header-right{display:flex;align-items:center;gap:12px;flex-shrink:0;}
.bell-icon{font-size:18px;color:var(--gold);cursor:pointer;position:relative;}
.notif-badge{
  position:absolute;top:-5px;right:-5px;
  background:var(--red);color:#fff;font-size:10px;font-weight:bold;
  width:16px;height:16px;border-radius:50%;
  display:none;justify-content:center;align-items:center;
  box-shadow:0 0 8px var(--red);
}
.header-wallet-btn{
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;padding:7px 14px;border-radius:20px;
  display:flex;align-items:center;gap:6px;
  font-weight:800;font-size:12px;cursor:pointer;
  white-space:nowrap;
  box-shadow:0 4px 12px rgba(255,165,0,0.4);
  transition:0.2s;
}
.header-wallet-btn:active{transform:scale(0.95);}

/* ====== SIDEBAR ====== */
.sidebar-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:900;display:none;}
.sidebar-overlay.active{display:block;}
.sidebar{
  position:fixed;top:0;left:-290px;width:270px;height:100vh;height:100dvh;
  background:linear-gradient(180deg, #15071f, #0a0312);
  z-index:1000;transition:left 0.3s cubic-bezier(0.4,0,0.2,1);
  display:flex;flex-direction:column;
  border-right:1px solid rgba(255,215,0,0.2);
  overflow-y:auto;
  box-shadow:5px 0 30px rgba(90,24,154,0.4);
}
.sidebar.active{left:0;}
.sidebar-header-section{
  padding:25px 20px;
  background:linear-gradient(135deg, rgba(157,78,221,0.3), rgba(90,24,154,0.4));
  border-bottom:1px solid rgba(255,215,0,0.2);
  display:flex;align-items:center;gap:15px;
}
.sidebar-avatar{
  width:54px;height:54px;
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;border-radius:50%;
  display:flex;justify-content:center;align-items:center;
  font-size:22px;font-weight:bold;flex-shrink:0;
  box-shadow:0 0 20px rgba(255,215,0,0.5);
}
.sidebar-menu{list-style:none;padding:20px 0;flex-grow:1;}
.sidebar-menu li{
  padding:14px 22px;font-size:14px;color:#c5b8e0;cursor:pointer;
  display:flex;align-items:center;gap:15px;
  border-left:3px solid transparent;
  transition:0.2s;
}
.sidebar-menu li:hover,.sidebar-menu li.active{background:rgba(157,78,221,0.2);color:#fff;border-left-color:var(--gold);}
.sidebar-menu li i{width:25px;text-align:center;color:var(--gold);}
.sidebar-footer{padding:20px;border-top:1px solid rgba(255,215,0,0.15);}
.logout-btn-sidebar{
  width:100%;padding:12px;
  background:linear-gradient(135deg, rgba(234,84,85,0.2), rgba(234,84,85,0.3));
  border:1px solid rgba(234,84,85,0.4);
  color:#fca5a5;font-weight:bold;border-radius:10px;cursor:pointer;
  display:flex;justify-content:center;align-items:center;gap:10px;
}

/* ====== PAGES ====== */
.page{display:none;padding:15px;padding-bottom:calc(95px + var(--safe-bottom));width:100%;}
.page.active{display:block;animation:fadeIn 0.4s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}

/* ====== SLIDER BOARD (Cyan Neon) ====== */
.slider-board{
  position:relative;border-radius:22px;overflow:hidden;
  margin-bottom:22px;
  border:2px solid rgba(0,229,255,0.4);
  box-shadow:0 0 30px rgba(0,229,255,0.3), inset 0 0 30px rgba(0,229,255,0.05);
  background:linear-gradient(135deg, #0a0312, #1a0730);
  height:200px;
}
.slider-track{display:flex;height:100%;transition:transform 0.5s cubic-bezier(0.4,0,0.2,1);}
.slider-slide{
  min-width:100%;height:100%;
  background-size:cover;background-position:center;
  display:flex;flex-direction:column;justify-content:flex-end;
  padding:22px;position:relative;
}
.slider-slide::before{
  content:'';position:absolute;top:0;left:0;width:100%;height:100%;
  background:linear-gradient(180deg, rgba(0,0,0,0.2), rgba(0,0,0,0.85));
  z-index:1;
}
.slider-content{position:relative;z-index:2;}
.slider-title{
  font-family:'Orbitron',sans-serif;
  font-size:22px;font-weight:900;
  background:linear-gradient(180deg,#FFD700 30%,#FFA500 70%,#B8860B 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  filter:drop-shadow(0 2px 8px rgba(157,78,221,0.8));
  margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;
}
.slider-sub{font-size:13px;color:#fff;margin-bottom:12px;}
.slider-btn{
  display:inline-flex;align-items:center;gap:8px;
  background:linear-gradient(135deg,#00E5FF,#0099CC);
  color:#001a22;padding:9px 22px;border-radius:30px;
  font-weight:800;font-size:13px;border:none;cursor:pointer;
  box-shadow:0 4px 15px rgba(0,229,255,0.5);
  font-family:'Orbitron',sans-serif;
}
.slider-dots{
  position:absolute;bottom:12px;right:20px;
  display:flex;gap:6px;z-index:3;
}
.slider-dot{
  width:8px;height:8px;border-radius:50%;
  background:rgba(255,255,255,0.3);
  transition:0.3s;
}
.slider-dot.active{
  background:var(--gold);
  box-shadow:0 0 10px var(--gold);
  width:22px;border-radius:4px;
}

/* ====== WINGO CARD ====== */
.wingo-big-card{
  background:linear-gradient(135deg, #1a0730 0%, #0a0312 100%);
  border:2px solid rgba(255,215,0,0.4);
  border-radius:22px;padding:20px;margin-bottom:22px;
  display:flex;align-items:center;gap:15px;
  cursor:pointer;flex-wrap:wrap;
  position:relative;overflow:hidden;
  box-shadow:0 8px 30px rgba(90,24,154,0.5);
}
.wingo-big-card::before{
  content:'';position:absolute;top:-50%;right:-50%;
  width:200%;height:200%;
  background:conic-gradient(from 0deg, transparent, rgba(255,215,0,0.15), transparent);
  animation:rotateGlow 6s linear infinite;
  pointer-events:none;
}
@keyframes rotateGlow{to{transform:rotate(360deg);}}
.wingo-logo-wrap{
  width:74px;height:74px;border-radius:18px;
  background:#000;display:flex;align-items:center;justify-content:center;
  overflow:hidden;flex-shrink:0;
  border:2px solid rgba(255,215,0,0.5);
  box-shadow:0 4px 12px rgba(15,23,42,.18);
  position:relative;z-index:1;
}
.wingo-logo-wrap img{width:100%;height:100%;object-fit:cover;}
.wingo-logo-wrap .default-wingo-icon{font-size:32px;color:var(--gold);}
.wingo-info{flex:1;min-width:0;position:relative;z-index:1;}
.wingo-info h3{
  font-family:'Orbitron',sans-serif;
  font-size:18px;font-weight:900;
  color:#f8fafc;
  margin-bottom:4px;
  filter:none;
}
.wingo-info p{font-size:12px;color:#a8a4b8;}
.wingo-play-btn{
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;padding:11px 20px;border-radius:30px;
  font-weight:800;font-size:12px;border:none;cursor:pointer;
  flex-shrink:0;
  box-shadow:0 3px 10px rgba(15,23,42,.18);
  position:relative;z-index:1;
  font-family:'Orbitron',sans-serif;
}

/* ====== SECTION TITLE ====== */
.section-title{
  display:flex;align-items:center;gap:10px;
  font-size:16px;font-weight:800;color:#fff;
  margin:22px 0 15px;padding-left:14px;
  border-left:3px solid var(--gold);
  position:relative;
}
.section-title::before{
  content:'';position:absolute;left:-1px;top:0;height:100%;
  width:3px;background:#94a3b8;
  box-shadow:none;
}
.section-title i{color:var(--gold);}
.section-title .provider-badge{
  font-size:10px;color:#cbd5e1;background:rgba(148,163,184,.12);
  padding:3px 10px;border-radius:20px;margin-left:auto;font-weight:600;
  border:1px solid rgba(148,163,184,.22);
}

/* ====== GAME GRID + BADGES ====== */
.game-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:20px;}
@media (min-width:480px){.game-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
.game-card{
  background:#111827;border-radius:10px;overflow:hidden;
  border:1px solid rgba(148,163,184,.22);
  cursor:pointer;min-width:0;
  position:relative;
  transition:0.3s;
}
.game-card:active{transform:scale(0.95);}
.game-card::after{
  content:'';position:absolute;inset:0;border-radius:12px;
  border:1px solid transparent;
  transition:0.3s;
  pointer-events:none;
}
.game-card:hover::after{border-color:rgba(148,163,184,.55);}
.game-thumb{width:100%;aspect-ratio:4/3;background:#0f172a;display:flex;justify-content:center;align-items:center;overflow:hidden;position:relative;}
.game-thumb img{width:100%;height:100%;object-fit:contain;object-position:center;display:block;background:#eef2f6;}
.game-name{
  padding:8px;font-size:10px;color:#f8fafc;text-align:center;
  font-weight:600;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;
  background:#111827;
}
body[data-theme="light"] .game-card{background:#fff;border-color:#d7dee8;box-shadow:0 5px 14px rgba(15,23,42,.06);}
body[data-theme="light"] .game-thumb{background:#eef2f6;}
body[data-theme="light"] .game-name{background:#fff;color:#172033;}
body[data-theme="light"] .game-name small{color:#475569 !important;}
body[data-theme="light"] .section-title{color:#172033;}
body[data-theme="light"] .section-title .provider-badge{color:#475569;background:#f1f5f9;border-color:#d7dee8;}
body[data-theme="light"] .header-right,body[data-theme="light"] .header-left,body[data-theme="light"] .sidebar-footer,body[data-theme="light"] .lb-item,body[data-theme="light"] .stat-box span,body[data-theme="light"] .stat-box h2,body[data-theme="light"] .wallet-card *{color:#172033;}
body[data-theme="light"] .header-wallet-btn,body[data-theme="light"] .wingo-play-btn{color:#fff;}
body[data-theme="light"] .wingo-logo-wrap{background:#eef2f6;border-color:#cbd5e1;}
body[data-theme="light"] .wingo-info h3{background:none;-webkit-text-fill-color:initial;color:#172033;}
body[data-theme="light"] .wingo-info p{color:#64748b;}
.game-badge{
  position:absolute;top:6px;right:6px;
  padding:3px 8px;border-radius:12px;
  font-size:9px;font-weight:900;
  font-family:'Orbitron',sans-serif;
  letter-spacing:0.5px;
  z-index:2;
  animation:none;
  text-transform:uppercase;
}
.game-badge.new{
  background:linear-gradient(135deg,#5cdb6a,#1a8a2e);
  color:#fff;
  box-shadow:0 0 12px rgba(92,219,106,0.7);
  text-shadow:0 1px 2px rgba(0,0,0,0.5);
}
.game-badge.hot{
  background:linear-gradient(135deg,#ff5e3a,#ff8c42);
  color:#fff;
  box-shadow:0 0 12px rgba(255,94,58,0.7);
  text-shadow:0 1px 2px rgba(0,0,0,0.5);
}
@keyframes badgePulse{
  0%,100%{transform:scale(1);}
  50%{transform:scale(1.1);}
}

/* Fire Icon (for hot games) */
.fire-icon{
  position:absolute;top:6px;left:6px;
  width:22px;height:22px;
  z-index:2;
  filter:drop-shadow(0 0 6px rgba(255,94,58,0.9));
  animation:fireFlicker 0.8s ease-in-out infinite;
}
@keyframes fireFlicker{
  0%,100%{transform:scale(1) rotate(-3deg);}
  50%{transform:scale(1.15) rotate(3deg);}
}

/* ====== LEADERBOARD ====== */
.leaderboard-section{
  background:var(--card-glass);
  border-radius:18px;padding:15px;margin-bottom:20px;
  border:1px solid rgba(157,78,221,0.3);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
}
.lb-header{
  display:flex;justify-content:space-between;align-items:center;
  margin-bottom:15px;border-bottom:1px solid rgba(255,215,0,0.15);
  padding-bottom:10px;
}
.lb-header h3{
  font-size:15px;
  background:linear-gradient(180deg,#FFD700,#FFA500);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  display:flex;align-items:center;gap:8px;
}
.lb-list{display:flex;flex-direction:column;gap:10px;max-height:200px;overflow:hidden;}
.lb-item{
  display:flex;justify-content:space-between;align-items:center;
  background:linear-gradient(135deg, rgba(157,78,221,0.15), rgba(0,0,0,0.4));
  padding:10px;border-radius:12px;gap:10px;
  border-left:3px solid var(--gold);
  animation:slideUp 0.5s ease;
}
@keyframes slideUp{from{opacity:0;transform:translateY(15px);}to{opacity:1;transform:translateY(0);}}
.lb-user{display:flex;align-items:center;gap:10px;font-size:12px;color:#ddd;min-width:0;flex:1;}
.lb-avatar{
  width:32px;height:32px;border-radius:50%;
  background:linear-gradient(135deg,#9D4EDD,#5A189A);
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;
  border:1px solid rgba(255,215,0,0.4);
  flex-shrink:0;
  color:#fff;
}
.lb-amount{
  color:var(--green);font-weight:bold;font-size:13px;white-space:nowrap;
  text-shadow:0 0 8px rgba(40,199,111,0.5);
}

/* ====== STATS ROW ====== */
.stats-row{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;}
.stat-box{
  background:var(--card-glass);
  padding:18px;border-radius:16px;
  border:1px solid rgba(157,78,221,0.3);
  min-width:0;
  position:relative;overflow:hidden;
}
.stat-box::before{
  content:'';position:absolute;top:0;right:0;
  width:60px;height:60px;border-radius:50%;
  background:radial-gradient(circle, rgba(255,215,0,0.15), transparent 70%);
  transform:translate(20px,-20px);
}
.stat-box span{display:block;color:#a8a4b8;font-size:11px;margin-bottom:5px;}
.stat-box h2{font-size:18px;word-break:break-all;position:relative;z-index:1;}
.text-green-stat{color:var(--green);}
.text-blue-stat{color:var(--cyan);}

/* ====== REFER CARD ====== */
.refer-card{
  background:rgba(20,10,35,0.6);
  border:1px dashed rgba(255,215,0,0.3);
  border-radius:20px;padding:40px 20px;text-align:center;
}
.refer-icon{font-size:60px;color:var(--purple);margin-bottom:20px;filter:drop-shadow(0 0 15px rgba(157,78,221,0.6));}
.step-text{font-size:14px;color:#c5b8e0;line-height:1.6;margin-bottom:5px;}
.step-text b{color:var(--gold);}
.step-green{color:var(--green);font-weight:bold;margin-top:10px;display:block;font-size:16px;text-shadow:0 0 10px rgba(40,199,111,0.5);}
.refer-code-box{
  background:#000;border:1px solid rgba(255,215,0,0.4);
  border-radius:12px;padding:15px;margin:30px 0;
  font-size:22px;font-weight:900;color:var(--gold);
  letter-spacing:2px;cursor:pointer;word-break:break-all;
  font-family:'Orbitron',sans-serif;
  box-shadow:0 0 20px rgba(255,215,0,0.3);
}
.share-btn-lg{
  width:100%;padding:15px;
  background:linear-gradient(90deg,#25D366,#128C7E);
  border:none;border-radius:12px;color:#fff;
  font-weight:bold;font-size:16px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:10px;
  box-shadow:0 4px 15px rgba(37,211,102,0.4);
}

/* ====== WALLET ====== */
.w-tab-container{display:flex;background:rgba(20,10,35,0.8);border-radius:12px;padding:5px;margin-bottom:20px;border:1px solid rgba(157,78,221,0.3);}
.w-tab-btn{flex:1;padding:12px;border:none;border-radius:9px;background:transparent;color:#a8a4b8;font-weight:bold;cursor:pointer;font-size:13px;transition:0.2s;}
.w-tab-btn.active{background:linear-gradient(90deg,#FFD700,#FFA500);color:#1a0a2e;}
.w-content-box{display:none;}
.w-content-box.active{display:block;}

.pay-method-tabs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;}
.pay-method-btn{
  padding:15px 10px;border-radius:14px;
  border:2px solid rgba(157,78,221,0.3);
  background:rgba(20,10,35,0.6);
  cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:8px;
  transition:0.2s;min-width:0;
}
.pay-method-btn.active{
  border-color:var(--gold);
  background:linear-gradient(135deg, rgba(157,78,221,0.3), rgba(90,24,154,0.4));
  box-shadow:0 0 20px rgba(255,215,0,0.3);
}
.pm-logo{
  width:70px;height:44px;border-radius:8px;
  display:flex;justify-content:center;align-items:center;
  font-weight:900;font-size:14px;overflow:hidden;
  background:#0a1a2a;color:#fff;
}
.pm-logo img{width:100%;height:100%;object-fit:contain;padding:3px;}
.pm-name{font-size:11px;color:#a8a4b8;font-weight:600;}
.pay-method-btn.active .pm-name{color:var(--gold);}

.pay-info-box{
  background:rgba(15,5,30,0.8);
  border:1px solid rgba(157,78,221,0.3);
  border-radius:14px;padding:15px;margin-bottom:15px;
}
.pay-info-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:12px 0;
  border-bottom:1px solid rgba(157,78,221,0.15);
  gap:10px;flex-wrap:wrap;
}
.pay-info-row:last-child{border-bottom:none;}
.pay-info-label{font-size:12px;color:#a8a4b8;white-space:nowrap;}
.pay-info-value-wrap{display:flex;align-items:center;gap:8px;min-width:0;}
.pay-info-value{font-size:14px;color:#fff;font-weight:bold;font-family:monospace;word-break:break-all;}
.copy-btn{
  background:rgba(157,78,221,0.2);
  border:1px solid rgba(157,78,221,0.4);
  color:var(--gold);padding:5px 10px;border-radius:8px;
  font-size:11px;cursor:pointer;flex-shrink:0;
}

.amount-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:15px;}
.amt-chip{
  background:rgba(20,10,35,0.6);
  border:1px solid rgba(157,78,221,0.3);
  color:#fff;padding:10px;border-radius:8px;
  cursor:pointer;font-size:12px;font-weight:bold;text-align:center;
  transition:0.2s;
}
.amt-chip:active{background:rgba(157,78,221,0.3);border-color:var(--gold);}

.input-group-bonus{margin-bottom:20px;}
.input-group-bonus label{color:#c5b8e0;font-size:12px;display:block;margin-bottom:8px;}
.bonus-input{
  width:100%;padding:15px;
  background:rgba(15,5,30,0.9);
  border:1px solid rgba(157,78,221,0.3);
  border-radius:12px;color:#fff;
  outline:none;font-weight:bold;font-size:14px;
}
.bonus-input:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(255,215,0,0.1);}
.bonus-input::placeholder{color:#5a4a75;font-weight:normal;}

.btn-submit-utr{
  width:100%;padding:15px;
  background:linear-gradient(90deg,#28c76f,#178a48);
  border:none;border-radius:12px;color:#fff;
  font-weight:800;font-size:14px;cursor:pointer;
  margin-top:20px;
  box-shadow:0 4px 15px rgba(40,199,111,0.4);
  display:flex;align-items:center;justify-content:center;gap:8px;
}
.btn-submit-utr:disabled{opacity:0.6;cursor:not-allowed;}
.bonus-btn-lg{
  width:100%;padding:15px;
  background:linear-gradient(90deg,#28c76f,#178a48);
  border:none;border-radius:12px;color:#fff;
  font-weight:800;font-size:14px;cursor:pointer;
  box-shadow:0 4px 15px rgba(40,199,111,0.4);
}
.bonus-btn-lg:disabled{opacity:0.5;cursor:not-allowed;}
.divider{height:1px;background:rgba(157,78,221,0.2);margin:25px 0;}
.info-txt{font-size:12px;color:#a8a4b8;margin-top:10px;line-height:1.5;}
.balance-card-mini{
  background:linear-gradient(135deg, rgba(157,78,221,0.3), rgba(90,24,154,0.4));
  padding:20px;border-radius:16px;
  border:1px solid rgba(255,215,0,0.3);
  margin-bottom:20px;
  display:flex;justify-content:space-between;align-items:center;gap:10px;
}

/* ====== BONUS PAGE ====== */
.bonus-gift-card{
  background:rgba(20,10,35,0.6);
  border:1px dashed rgba(255,215,0,0.3);
  border-radius:20px;padding:40px 20px;text-align:center;
}
.gift-icon-container i{
  font-size:60px;color:var(--gold);margin-bottom:15px;
  filter:drop-shadow(0 0 15px rgba(255,215,0,0.6));
  animation:giftBounce 2s ease-in-out infinite;
}
@keyframes giftBounce{0%,100%{transform:translateY(0);}50%{transform:translateY(-8px);}}
.bonus-instruction{color:#c5b8e0;font-size:14px;margin-bottom:30px;}

/* ====== NOTIFICATIONS ====== */
.notif-item{
  background:rgba(20,10,35,0.6);
  padding:15px;border-radius:12px;
  border:1px solid rgba(157,78,221,0.3);
  margin-bottom:15px;
  border-left:3px solid var(--gold);
}
.notif-title{color:var(--gold);font-weight:bold;font-size:15px;margin-bottom:5px;}
.notif-body{color:#ddd;font-size:13px;line-height:1.5;word-wrap:break-word;}
.notif-time{color:#7a6b95;font-size:11px;margin-top:10px;display:block;text-align:right;}

/* ====== NAVBAR ====== */
.navbar{
  position:fixed;bottom:0;left:50%;transform:translateX(-50%);
  width:100%;max-width:480px;
  background:linear-gradient(180deg, rgba(20,10,35,0.95), rgba(5,2,8,0.98));
  backdrop-filter:blur(15px);-webkit-backdrop-filter:blur(15px);
  border-top:1px solid rgba(255,215,0,0.2);
  display:flex;justify-content:space-around;
  padding:10px 0 calc(10px + var(--safe-bottom));
  z-index:100;transition:transform 0.3s;
  box-shadow:0 -4px 20px rgba(90,24,154,0.4);
}
.navbar.hidden{transform:translate(-50%,100%);}
.nav-item{
  display:flex;flex-direction:column;align-items:center;gap:4px;
  color:#7a6b95;cursor:pointer;font-size:10px;
  background:none;border:none;min-width:55px;padding:4px;
  transition:0.2s;
}
.nav-item i{font-size:18px;}
.nav-item.active{
  color:var(--gold);
  filter:drop-shadow(0 0 8px rgba(255,215,0,0.5));
}

/* ====== TAGS ====== */
.tag-pending{color:#ffc107;border:1px solid #ffc107;background:rgba(255,193,7,0.1);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;white-space:nowrap;}
.tag-success{color:#00e676;border:1px solid #00e676;background:rgba(0,230,118,0.1);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;white-space:nowrap;}
.tag-auto{color:#3b82f6;border:1px solid #3b82f6;background:rgba(59,130,246,0.1);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;white-space:nowrap;}
.tag-rejected{color:#ea5455;border:1px solid #ea5455;background:rgba(234,84,85,0.1);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:bold;white-space:nowrap;}
.hist-item{
  display:block;
  background:rgba(20,10,35,0.6);
  padding:15px;border-radius:12px;
  margin-bottom:10px;
  border-left:4px solid #fff;
}
.hist-item.Deposit{border-left-color:var(--green);}
.hist-item.Withdraw{border-left-color:var(--red);}
.text-yellow{color:#ffc107!important;}
.text-red{color:#ea5455!important;}
.text-green{color:#00e676!important;}

/* ====== WINGO GAME ====== */
#wingo-game-container{
  position:fixed;top:0;left:50%;transform:translateX(-50%);
  width:100%;max-width:480px;height:100vh;height:100dvh;
  background:var(--wingo-bg, linear-gradient(180deg,#0a0a12 0%,#14141f 50%,#0a0a12 100%));
  background-size:cover;background-position:center;background-repeat:no-repeat;
  z-index:999;display:none;overflow-y:auto;-webkit-overflow-scrolling:touch;
}
#wingo-game-container.active{display:block;}
#wingo-game-container::before{
  content:'';position:absolute;top:0;left:0;width:100%;height:100%;
  background:rgba(0,0,0,0.5);z-index:0;display:none;
}
#wingo-game-container.has-bg::before{display:block;}
#wingo-game-container > *{position:relative;z-index:1;}
body.has-bg #app-content{background:rgba(243,246,250,.88);}
body.has-bg[data-theme="dark"] #app-content{background:rgba(243,246,250,.88);}

.wingo-header{
  background:linear-gradient(90deg, rgba(90,24,154,0.9), rgba(40,10,70,0.95));
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  padding:15px 18px;padding-top:calc(15px + var(--safe-top));
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;z-index:50;
  border-bottom:1px solid rgba(255,215,0,0.3);
}
.wingo-header .header-title{
  font-family:'Orbitron',sans-serif;
  font-size:17px;font-weight:900;
  background:linear-gradient(90deg,#FFD700,#FFA500);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  filter:drop-shadow(0 2px 6px rgba(157,78,221,0.8));
}
.wingo-header .header-icon{
  font-size:20px;cursor:pointer;color:var(--gold);
  width:38px;height:38px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  background:rgba(157,78,221,0.25);
}
.wallet-section{
  background:linear-gradient(135deg,rgba(255,215,0,0.15),rgba(157,78,221,0.15));
  margin:12px 15px;padding:22px 20px;border-radius:18px;
  text-align:center;
  border:1px solid rgba(255,215,0,0.3);
  backdrop-filter:blur(10px);
}
.wallet-bal-label{color:var(--gold);font-size:12px;margin-bottom:8px;}
.wallet-amount{
  font-size:30px;font-weight:900;margin-bottom:20px;
  background:linear-gradient(90deg,#FFD700,#FFED4E,#FFD700);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;word-break:break-all;
  filter:drop-shadow(0 0 15px rgba(255,215,0,0.5));
}
.wallet-btns{display:flex;gap:12px;}
.w-btn{flex:1;padding:13px;border-radius:12px;border:none;font-size:14px;font-weight:700;color:#fff;cursor:pointer;}
.w-btn-deposit{background:linear-gradient(135deg,#28c76f,#1a9c54);box-shadow:0 4px 15px rgba(40,199,111,0.4);}
.w-btn-withdraw{background:linear-gradient(135deg,#ea5455,#b8393a);box-shadow:0 4px 15px rgba(234,84,85,0.4);}
.notice-bar{
  background:rgba(157,78,221,0.2);
  margin:0 15px 15px;padding:10px 15px;border-radius:12px;
  display:flex;align-items:center;gap:10px;font-size:11px;
  border:1px solid rgba(157,78,221,0.3);
  color:var(--gold);overflow:hidden;
}
.time-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:0 15px;margin-bottom:18px;}
.time-tab{
  background:linear-gradient(135deg, rgba(157,78,221,0.2), rgba(20,10,35,0.6));
  border-radius:14px;padding:12px 5px;text-align:center;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:5px;
  border:1px solid rgba(157,78,221,0.3);min-width:0;
  transition:0.3s;
}
.time-tab .clock-icon{font-size:22px;color:#7a6b95;}
.tab-text{font-size:10px;color:#a8a4b8;line-height:1.3;}
.time-tab.active{
  background:linear-gradient(180deg,#FFD700,#FFA500);
  border-color:var(--gold);
  box-shadow:0 0 20px rgba(255,215,0,0.4);
}
.time-tab.active .clock-icon,.time-tab.active .tab-text{color:#1a0a2e;font-weight:800;}
.timer-card{
  background:linear-gradient(135deg, rgba(20,10,35,0.85), rgba(40,10,70,0.7));
  margin:0 15px 18px;border-radius:16px;display:flex;
  border:1px solid rgba(255,215,0,0.2);
  overflow:hidden;
  backdrop-filter:blur(10px);
}
.timer-left{width:55%;padding:16px;border-right:1px dashed rgba(255,215,0,0.2);min-width:0;}
.how-to-play-btn{
  border:1px solid var(--gold);color:var(--gold);
  padding:4px 12px;border-radius:20px;font-size:10px;
  display:inline-flex;align-items:center;gap:5px;margin-bottom:10px;
  background:rgba(255,215,0,0.08);
}
.period-txt{font-size:11px;color:var(--gold);margin-bottom:4px;}
.period-num{font-size:14px;font-weight:800;letter-spacing:1px;color:#fff;word-break:break-all;}
.timer-right{width:45%;padding:16px;text-align:right;min-width:0;}
.time-rem-txt{font-size:11px;color:var(--gold);margin-bottom:6px;}
.countdown-box{display:flex;justify-content:flex-end;align-items:center;gap:4px;}
.c-box{
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;font-weight:900;font-size:16px;
  padding:5px 7px;border-radius:6px;min-width:28px;text-align:center;
  box-shadow:0 0 10px rgba(255,215,0,0.4);
}
.game-area{padding:0 15px;margin-bottom:20px;position:relative;}
.game-area.locked{opacity:0.5;pointer-events:none;}
.countdown-overlay-box{
  position:absolute;top:0;left:0;width:100%;height:100%;z-index:20;
  display:none;justify-content:center;align-items:center;gap:15px;
  background:rgba(0,0,0,0.7);border-radius:16px;
}
.cd-card{
  width:70px;height:90px;
  background:linear-gradient(135deg,#1a0a2e,#2a0e4e);
  border:2px solid var(--gold);border-radius:14px;
  display:flex;justify-content:center;align-items:center;
  font-size:50px;font-weight:900;color:var(--gold);
  box-shadow:0 0 30px rgba(255,215,0,0.5);
}
.color-btns{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:15px;}
.c-btn{padding:14px 5px;border:none;color:#fff;font-weight:800;font-size:13px;cursor:pointer;}
.btn-g{background:linear-gradient(135deg,#28c76f,#178a48);border-radius:8px 22px 8px 8px;box-shadow:0 4px 15px rgba(40,199,111,0.4);}
.btn-v{background:linear-gradient(135deg,#9c27b0,#6a1b9a);border-radius:8px;box-shadow:0 4px 15px rgba(156,39,176,0.4);}
.btn-r{background:linear-gradient(135deg,#ea5455,#c0392b);border-radius:22px 8px 8px 8px;box-shadow:0 4px 15px rgba(234,84,85,0.4);}
.number-grid{
  display:grid;grid-template-columns:repeat(5,1fr);gap:10px;
  background:linear-gradient(135deg, rgba(20,10,35,0.85), rgba(40,10,70,0.7));
  padding:14px;border-radius:16px;margin-bottom:15px;
  border:1px solid rgba(255,215,0,0.2);
  backdrop-filter:blur(10px);
}
.num-btn{aspect-ratio:1;border-radius:50%;border:none;cursor:pointer;color:#fff;font-size:18px;font-weight:700;padding:0;}
.n0{background:linear-gradient(135deg,#ea5455 50%,#9c27b0 50%);}
.n1,.n3,.n7,.n9{background:linear-gradient(135deg,#28c76f,#178a48);}
.n2,.n4,.n6,.n8{background:linear-gradient(135deg,#ea5455,#c0392b);}
.n5{background:linear-gradient(135deg,#28c76f 50%,#9c27b0 50%);}
.bs-btns{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;}
.bs-btn{padding:14px;border:none;border-radius:50px;font-size:16px;font-weight:800;color:#fff;cursor:pointer;}
.btn-big{background:linear-gradient(135deg,#FFC107,#E6A800);color:#1a0a2e;box-shadow:0 4px 15px rgba(255,193,7,0.4);}
.btn-small{background:linear-gradient(135deg,#3d8bff,#2965c0);box-shadow:0 4px 15px rgba(61,139,255,0.4);}

.records-container{
  background:linear-gradient(135deg, rgba(20,10,35,0.85), rgba(40,10,70,0.7));
  margin:0 15px 80px;border-radius:16px;padding-bottom:20px;
  min-height:400px;
  border:1px solid rgba(255,215,0,0.2);
  backdrop-filter:blur(10px);
}
.r-tabs{display:flex;background:rgba(10,5,20,0.9);padding:5px;border-radius:16px 16px 0 0;}
.r-tab{flex:1;padding:10px;text-align:center;color:#a8a4b8;font-size:13px;font-weight:600;cursor:pointer;border-radius:10px;}
.r-tab.active{background:linear-gradient(135deg,#FFD700,#FFA500);color:#1a0a2e;}
.gh-table{width:100%;border-collapse:collapse;text-align:center;font-size:12px;}
.gh-table th{color:var(--gold);padding:10px;border-bottom:1px solid rgba(255,215,0,0.2);}
.gh-table td{padding:10px;border-bottom:1px solid rgba(157,78,221,0.15);}
.dot-mix-red-violet{width:12px;height:12px;border-radius:50%;margin:0 auto;background:linear-gradient(135deg,#ea5455 50%,#9c27b0 50%);}
.dot-mix-green-violet{width:12px;height:12px;border-radius:50%;margin:0 auto;background:linear-gradient(135deg,#28c76f 50%,#9c27b0 50%);}
.dot-single{width:10px;height:10px;border-radius:50%;margin:0 auto;}
.pagination-box{display:flex;justify-content:space-between;align-items:center;padding:15px 20px;background:rgba(10,5,20,0.9);}
.pg-btn{
  width:40px;height:40px;border-radius:10px;border:none;
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;font-size:18px;cursor:pointer;
  box-shadow:0 4px 12px rgba(255,165,0,0.4);
}
.pg-info{font-size:14px;font-weight:bold;color:var(--gold);}
.chart-header-row{display:flex;background:linear-gradient(90deg,#FFD700,#FFA500);color:#1a0a2e;font-size:12px;font-weight:bold;padding:10px 0;}
.ch-period{width:30%;text-align:center;}
.ch-number{width:70%;text-align:center;}
.chart-scroll{overflow-x:auto;position:relative;}
.c-row{display:flex;align-items:center;height:35px;border-bottom:1px solid rgba(157,78,221,0.15);}
.c-period{width:30%;font-size:12px;text-align:center;color:var(--gold);}
.c-nums{width:70%;display:flex;justify-content:space-around;align-items:center;padding:0 10px;}
.c-num{
  width:20px;height:20px;border-radius:50%;
  border:1px solid rgba(157,78,221,0.3);
  color:#7a6b95;font-size:11px;
  display:flex;justify-content:center;align-items:center;
  background:#0a0a12;
}
.c-num.win{color:#fff;border:none;font-weight:bold;}
.c-num.win.red{background:#ea5455;}
.c-num.win.green{background:#28c76f;}
.c-num.win.mix0{background:linear-gradient(135deg,#ea5455 50%,#9c27b0 50%);}
.c-num.win.mix5{background:linear-gradient(135deg,#28c76f 50%,#9c27b0 50%);}
.c-result-icon{
  width:18px;height:18px;border-radius:50%;
  font-size:10px;display:flex;justify-content:center;align-items:center;
  color:#fff;font-weight:bold;margin-left:5px;
}
.icon-B{background:#ffc107;color:#1a0a2e;}
.icon-S{background:#3d8bff;}
.chart-svg{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;}
.mb-item{
  display:flex;align-items:center;
  background:rgba(10,5,20,0.6);
  border-radius:10px;padding:15px;margin-bottom:10px;
  border:1px solid rgba(157,78,221,0.2);
}
.mb-icon{
  width:50px;height:50px;border-radius:12px;
  display:flex;justify-content:center;align-items:center;
  font-weight:700;font-size:13px;color:#fff;margin-right:15px;flex-shrink:0;
}
.box-Small{background:#5da0e5;}
.box-Big{background:#eda134;}
.box-Green{background:#28c76f;}
.box-Red{background:#ea5455;}
.box-Violet{background:#9c27b0;}
.box-Num{background:#4b586e;}
.mb-details{flex-grow:1;min-width:0;}
.mb-period{font-size:14px;font-weight:600;color:#fff;word-break:break-all;}
.mb-time{font-size:11px;color:#7a6b95;}
.mb-right{text-align:right;flex-shrink:0;}
.mb-status-btn{display:inline-block;padding:3px 12px;border-radius:6px;font-size:11px;}
.st-pending{border:1px solid #ffc107;color:#ffc107;}
.st-failed{border:1px solid #ea5455;color:#ea5455;}
.st-success{border:1px solid #28c76f;color:#28c76f;}
.mb-amt{font-size:14px;font-weight:600;}
.text-plus{color:#28c76f;}
.text-minus{color:#ea5455;}
.text-wait{color:#a8a4b8;}

/* ====== BET SHEET ====== */
.bet-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:2000;display:none;}
.bet-overlay.active{display:block;}
.bet-sheet{
  position:fixed;bottom:0;left:50%;transform:translate(-50%,100%);
  width:100%;max-width:480px;
  background:linear-gradient(180deg,#1a0a2e,#0a0312);
  z-index:2001;transition:0.3s;
  border-radius:24px 24px 0 0;
  border-top:3px solid var(--gold);
  box-shadow:0 -10px 40px rgba(255,215,0,0.3);
}
.bet-sheet.active{transform:translate(-50%,0);}
.bs-head{
  background:linear-gradient(90deg,#FFD700,#FFA500);
  padding:15px;text-align:center;font-weight:bold;font-size:16px;
  border-radius:24px 24px 0 0;color:#1a0a2e;
  font-family:'Orbitron',sans-serif;
}
.bs-select-display{
  background:#000;color:var(--gold);
  padding:5px 30px;border-radius:10px;display:inline-block;
  margin-top:10px;font-size:18px;font-weight:900;
  border:1px solid var(--gold);
}
.bs-body{padding:25px 20px;}
.bs-row{display:flex;gap:10px;margin-bottom:20px;align-items:center;flex-wrap:wrap;}
.money-btn{
  flex:1;min-width:60px;
  background:rgba(20,10,35,0.8);
  color:#a8a4b8;
  border:1px solid rgba(157,78,221,0.3);
  padding:10px;border-radius:8px;font-weight:bold;cursor:pointer;
}
.money-btn.active{
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;border-color:var(--gold);
  box-shadow:0 0 15px rgba(255,215,0,0.4);
}
.qty-box{display:flex;align-items:center;gap:10px;}
.qty-btn{
  width:32px;height:32px;
  background:linear-gradient(135deg,#FFD700,#FFA500);
  border:none;color:#1a0a2e;border-radius:8px;
  font-size:18px;cursor:pointer;font-weight:900;
}
.qty-val{
  background:rgba(20,10,35,0.8);
  border:1px solid rgba(157,78,221,0.3);
  padding:5px 15px;border-radius:8px;
  color:var(--gold);font-weight:700;
}
.bs-foot{display:flex;}
.bs-cancel{
  flex:1;background:rgba(20,10,35,0.8);
  color:var(--gold);border:none;padding:15px;
  font-weight:bold;cursor:pointer;
  border-top:1px solid rgba(255,215,0,0.2);
}
.bs-ok{
  flex:2;
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;border:none;padding:15px;
  font-weight:900;cursor:pointer;
  font-family:'Orbitron',sans-serif;
}

/* ====== WIN/LOSS POPUP ====== */
.win-popup{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:2050;display:none;justify-content:center;align-items:center;}
.win-card{
  width:340px;max-width:90%;
  background:linear-gradient(180deg,#ff5e3a,#ff9a68);
  border-radius:24px;text-align:center;padding-bottom:30px;
  animation:winPop 0.4s ease;
  box-shadow:0 20px 60px rgba(255,94,58,0.5);
}
@keyframes winPop{from{transform:scale(0.6);opacity:0;}to{transform:scale(1);opacity:1;}}
.win-header-deco{
  height:100px;
  background:url('https://cdn-icons-png.flaticon.com/512/3135/3135768.png') no-repeat center/80px;
  margin-top:20px;
}
.win-title{font-size:26px;font-weight:900;margin-bottom:20px;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,0.3);}
.win-res-row{display:flex;justify-content:center;gap:5px;margin-bottom:20px;flex-wrap:wrap;}
.win-pill{padding:5px 12px;border-radius:6px;font-weight:bold;font-size:14px;color:#fff;}
.win-bonus-box{background:#fff;width:80%;margin:0 auto 20px;padding:15px;border-radius:12px;}
.win-label-bonus{font-size:13px;color:#888;font-weight:bold;display:block;margin-bottom:5px;}
.win-amount{font-size:34px;font-weight:900;color:#ff5e3a;display:block;}
.win-close-timer{font-size:12px;color:rgba(255,255,255,0.8);}
.popup-loss{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:2050;display:none;justify-content:center;align-items:center;}
.loss-card{
  width:300px;max-width:90%;
  background:linear-gradient(180deg,#333,#111);
  border-radius:24px;padding:40px 20px;text-align:center;
  border:1px solid #555;
}
.loss-title{font-size:24px;font-weight:900;color:#ccc;margin-bottom:10px;}
.loss-res{color:#888;font-size:14px;margin-bottom:20px;}
.loss-btn{
  border:1px solid #666;background:transparent;color:#ccc;
  padding:8px 30px;border-radius:20px;cursor:pointer;
}

#toast{
  visibility:hidden;min-width:250px;max-width:90%;
  background:rgba(20,10,35,0.98);
  color:#fff;text-align:center;padding:16px;
  position:fixed;z-index:3000;left:50%;bottom:100px;
  transform:translateX(-50%);font-size:14px;
  border-radius:12px;border:1px solid var(--gold);
  box-shadow:0 0 20px rgba(255,215,0,0.3);
}
#toast.show{visibility:visible;}

/* ====== DEMO OVERLAY ====== */
#demo-game-overlay{
  position:fixed;top:0;left:50%;transform:translateX(-50%);
  width:100%;max-width:480px;height:100vh;height:100dvh;
  background:#000;z-index:9999;display:none;flex-direction:column;
}
#demo-game-overlay.active{display:flex;}
.demo-header{
  background:linear-gradient(90deg, rgba(90,24,154,0.9), rgba(40,10,70,0.95));
  padding:12px 15px;
  padding-top:calc(12px + var(--safe-top));
  display:flex;justify-content:space-between;align-items:center;
  border-bottom:1px solid rgba(255,215,0,0.3);
}
.demo-header .title{font-size:14px;font-weight:700;color:var(--gold);}
.demo-header .close-btn{
  background:rgba(157,78,221,0.3);
  border:none;color:#fff;
  width:36px;height:36px;border-radius:50%;
  font-size:16px;cursor:pointer;
  display:flex;justify-content:center;align-items:center;
}
#demo-game-frame{flex:1;width:100%;border:none;background:#000;}

.floating-cs-btn{
  position:fixed;bottom:100px;right:20px;
  width:60px;height:60px;
  background:linear-gradient(135deg,#42e695,#3bb2b8);
  border-radius:50%;
  display:none;justify-content:center;align-items:center;
  box-shadow:0 4px 15px rgba(66,230,149,0.5);
  z-index:400;cursor:pointer;border:2px solid #fff;
}
.sound-toggle{
  position:fixed;top:60px;right:15px;
  width:42px;height:42px;
  background:rgba(157,78,221,0.3);
  border:1px solid var(--gold);
  border-radius:50%;
  display:flex;justify-content:center;align-items:center;
  color:var(--gold);font-size:16px;cursor:pointer;
  z-index:200;backdrop-filter:blur(5px);
  box-shadow:0 0 15px rgba(255,215,0,0.3);
}
.sound-toggle.muted{color:#666;border-color:#333;box-shadow:none;}
#loading-overlay{background:#080d18;gap:18px;}
.cyan-spinner{width:0;height:0;display:none;}
.cyan-spinner .dot{display:none;}
.loading-text{font-family:'Poppins','Padauk',sans-serif;color:#dbe5ef;font-size:14px;letter-spacing:2px;text-shadow:none;animation:none;}
#loading-overlay::after{content:'';display:block;width:min(62vw,420px);height:5px;border-radius:99px;background:linear-gradient(90deg,var(--lobby-accent),var(--lobby-accent-2));}

/* ===== HTDOCS-INSPIRED LOBBY SHELL =====
   The Cocos htdocs build is a compiled canvas, so this keeps its dark arcade
   atmosphere while using the existing editable website handlers and routes. */
:root{--lobby-bg:#080d18;--lobby-panel:#101827;--lobby-panel-2:#141f31;--lobby-line:#243247;--lobby-text:#f8fafc;--lobby-muted:#94a3b8;--lobby-accent:#39d0b5;--lobby-accent-2:#5b8cff;}
body{background:var(--lobby-bg);color:var(--lobby-text);}
.app-container,#app-content{max-width:1200px;}
#app-content{background:linear-gradient(180deg,#0b1220 0%,#080d18 42%,#080d18 100%);}
header{background:rgba(10,18,31,.97);border-bottom:1px solid var(--lobby-line);box-shadow:0 8px 24px rgba(0,0,0,.20);padding:14px 22px;}
.menu-btn{background:#162235;color:var(--lobby-accent);border-radius:10px;width:36px;height:36px;}
.user-greeting{background:none;-webkit-text-fill-color:initial;color:var(--lobby-text);font-weight:600;}
.header-wallet-btn{background:var(--lobby-accent);color:#07131a;box-shadow:none;border-radius:8px;padding:8px 14px;}
.page{padding:22px 28px 110px;}
.slider-board{border:1px solid var(--lobby-line);border-radius:14px;box-shadow:0 12px 30px rgba(0,0,0,.24);}
.slider-slide{background-color:#172235;}
.slider-slide::before{background:linear-gradient(90deg,rgba(8,13,24,.88),rgba(8,13,24,.20));}
.slider-title{font-family:'Poppins','Padauk',sans-serif;letter-spacing:.5px;text-shadow:none;}
.slider-sub{color:#dbe5ef;}
.slider-btn{background:var(--lobby-accent);color:#07131a;box-shadow:none;border-radius:8px;font-family:inherit;}
.slider-dot{background:#64748b;box-shadow:none;}
.slider-dot.active{background:var(--lobby-accent);box-shadow:none;}
.wingo-big-card{background:linear-gradient(135deg,#15243a,#101827);border:1px solid var(--lobby-line);box-shadow:0 10px 24px rgba(0,0,0,.18);border-radius:14px;}
.wingo-big-card::before{display:none;}
.wingo-logo-wrap{border-color:#34465d;box-shadow:none;background:#0c1422;}
.wingo-info h3{font-family:inherit;background:none;-webkit-text-fill-color:initial;color:var(--lobby-text);filter:none;}
.wingo-info p{color:var(--lobby-muted);}
.wingo-play-btn{background:var(--lobby-accent);color:#07131a;box-shadow:none;border-radius:8px;font-family:inherit;}
.section-title{color:var(--lobby-text);border-left-color:var(--lobby-accent);margin-top:28px;}
.section-title::before{background:var(--lobby-accent);}
.section-title i{color:var(--lobby-accent);}
.section-title .provider-badge{color:#b7c7d8;background:#152235;border-color:#2b4058;}
.game-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;}
.game-card{background:var(--lobby-panel);border:1px solid var(--lobby-line);border-radius:12px;box-shadow:0 8px 18px rgba(0,0,0,.14);transition:transform .18s ease,border-color .18s ease;}
.game-card:hover{transform:translateY(-2px);}
.game-card:hover::after{border-color:var(--lobby-accent);}
.game-thumb{aspect-ratio:16/10;background:#eef2f6;}
.game-thumb img{object-fit:contain;object-position:center;width:100%;height:100%;padding:0;}
.game-name{background:var(--lobby-panel);color:#e2e8f0;padding:10px 8px;font-size:11px;}
.game-badge{animation:none;box-shadow:none;}
.bottom-nav{background:rgba(10,18,31,.98);border-top:1px solid var(--lobby-line);box-shadow:0 -8px 24px rgba(0,0,0,.22);}
.nav-item{color:var(--lobby-muted);}
.nav-item.active,.nav-item:hover{color:var(--lobby-accent);}
.nav-item i{filter:none;}
.icon-image{display:inline-block!important;width:1.25em;height:1.25em;background-position:center;background-repeat:no-repeat;background-size:contain;vertical-align:-.2em;font-size:inherit;}
.sidebar{background:#0d1726;border-right:1px solid var(--lobby-line);box-shadow:8px 0 28px rgba(0,0,0,.28);}
.sidebar-header-section{background:#111e30;border-bottom:1px solid var(--lobby-line);}
.sidebar-menu li{color:#9fb0c3;}
.sidebar-menu li:hover,.sidebar-menu li.active{background:#17263a;color:#fff;border-left-color:var(--lobby-accent);}
.theme-toggle{color:var(--lobby-accent);background:#162235;border-color:#2b4058;}
@media (min-width:700px){.game-grid{grid-template-columns:repeat(4,minmax(0,1fr));}.slider-board{height:280px;}.wingo-big-card{padding:18px 22px;}.bottom-nav{max-width:1200px;left:50%;transform:translateX(-50%);border-left:1px solid var(--lobby-line);border-right:1px solid var(--lobby-line);}}
@media (min-width:1040px){.game-grid{grid-template-columns:repeat(6,minmax(0,1fr));}.page{padding-left:42px;padding-right:42px;}}
body[data-theme="light"]{--lobby-bg:#f3f6fa;--lobby-panel:#fff;--lobby-panel-2:#fff;--lobby-line:#d8e0ea;--lobby-text:#172033;--lobby-muted:#64748b;--lobby-accent:#0f766e;background:#f3f6fa;color:#172033;}
body[data-theme="light"] #app-content{background:#f3f6fa;}
body[data-theme="light"] header,body[data-theme="light"] .bottom-nav{background:rgba(255,255,255,.97);border-color:var(--lobby-line);}
body[data-theme="light"] .header-wallet-btn,body[data-theme="light"] .slider-btn,body[data-theme="light"] .wingo-play-btn{background:#0f766e;color:#fff;}
body[data-theme="light"] .slider-slide::before{background:linear-gradient(90deg,rgba(15,23,42,.68),rgba(15,23,42,.12));}
body[data-theme="light"] .wingo-big-card,body[data-theme="light"] .game-card{background:#fff;border-color:var(--lobby-line);}
body[data-theme="light"] .game-name{background:#fff;color:#172033;}
body[data-theme="light"] .game-thumb{background:#edf2f7;}
body[data-theme="light"] .section-title{color:#172033;border-left-color:#0f766e;}
body[data-theme="light"] .section-title::before{background:#0f766e;}
body[data-theme="light"] .section-title i{color:#0f766e;}
body[data-theme="light"] .sidebar{background:#fff;border-right-color:var(--lobby-line);}
body[data-theme="light"] .sidebar-header-section{background:#f8fafc;border-bottom-color:var(--lobby-line);}
body[data-theme="light"] .sidebar-menu li{color:#64748b;}
body[data-theme="light"] .sidebar-menu li:hover,body[data-theme="light"] .sidebar-menu li.active{background:#edf6f5;color:#172033;border-left-color:#0f766e;}
/* Final player mode: white theme only. */
body,body[data-theme="dark"]{--lobby-bg:#f3f6fa;--lobby-panel:#fff;--lobby-panel-2:#fff;--lobby-line:#d8e0ea;--lobby-text:#172033;--lobby-muted:#64748b;--lobby-accent:#0f766e;background:#f3f6fa;color:#172033;}
body[data-theme="dark"] #app-content{background:#f3f6fa;}
body[data-theme="dark"] header,body[data-theme="dark"] .bottom-nav{background:rgba(255,255,255,.97);border-color:#d8e0ea;}
body[data-theme="dark"] .wingo-big-card,body[data-theme="dark"] .game-card{background:#fff;border-color:#d8e0ea;}
/* Web-shell-only polish. Embedded Buffalo/Wingo game UI is intentionally untouched. */
header{position:sticky;top:0;z-index:120;backdrop-filter:blur(12px);}
.page > h2{color:#172033;font-weight:800;letter-spacing:-.2px;}
.w-tab-container{background:#fff;border:1px solid #d8e0ea;border-radius:12px;padding:4px;box-shadow:0 5px 14px rgba(15,23,42,.06);}
.w-tab-btn{border-radius:9px;transition:background .18s ease,color .18s ease,box-shadow .18s ease;}
.w-tab-btn.active{background:#111827;color:#fff;box-shadow:0 4px 10px rgba(15,23,42,.16);}
.w-content-box{border:1px solid #d8e0ea;border-radius:12px;background:#fff;box-shadow:0 8px 20px rgba(15,23,42,.06);}
.btn-primary{border-radius:9px;box-shadow:0 5px 12px rgba(15,118,110,.18);}
.stat-box,.leaderboard-section,.wallet-card,.refer-card,.bonus-card,.history-card{border-radius:12px;}
.rules-card{background:#fff;border:1px solid #d8e0ea;border-radius:14px;padding:16px 18px;margin-bottom:14px;box-shadow:0 8px 20px rgba(15,23,42,.06);color:#172033;line-height:1.7;}
.rules-card h3{font-size:16px;margin-bottom:8px;color:#0f766e;}
.rules-card p{font-size:13px;margin:4px 0;color:#475569;}
.rules-safe{border-left:4px solid #0f766e;}
.turnover-board{background:#fff;border:1px solid #111827;border-radius:14px;padding:15px 16px;margin-bottom:16px;box-shadow:0 8px 20px rgba(15,23,42,.08);color:#172033;}
.turnover-board-title{font-weight:800;font-size:15px;margin-bottom:12px;color:#0f172a;}
.turnover-row{display:flex;justify-content:space-between;gap:10px;font-size:12px;color:#64748b;margin-top:9px;}
.turnover-row b{color:#172033;font-size:12px;}
.turnover-track{height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin-top:6px;}
.turnover-track span{display:block;height:100%;width:0;background:linear-gradient(90deg,#0f766e,#14b8a6);border-radius:99px;transition:width .25s ease;}
.turnover-remaining{margin-top:12px;font-size:12px;color:#0f766e;font-weight:700;}
.member-bonus-page-card{background:linear-gradient(135deg,#fff7ed,#ecfeff);border:1px solid #0f766e;border-radius:14px;padding:16px;margin-bottom:16px;color:#172033;box-shadow:0 8px 20px rgba(15,23,42,.08);}
.member-bonus-page-card p{font-size:12px;color:#475569;line-height:1.6;margin:8px 0;}
.icon-pack-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0 14px;}
.icon-pack-item{border:1px solid #d8e0ea;border-radius:10px;padding:8px;background:#f8fafc;text-align:center;font-size:11px;color:#475569;}
.icon-pack-item input{display:block;width:100%;font-size:9px;margin-top:5px;}
.icon-pack-item img{display:block;width:30px;height:30px;object-fit:contain;margin:6px auto 0;border-radius:6px;}
.icon-image{font-family:initial!important;font-size:0!important;background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;color:transparent!important;}
.icon-image::before,.icon-image::after{content:none!important;display:none!important;}
.icon-image-element{display:inline-block!important;width:1em!important;height:1em!important;max-width:28px;max-height:28px;object-fit:contain;vertical-align:middle;}
.nav-item .icon-image-element{width:20px!important;height:20px!important;}
.remove-bg-tool{border:1px solid #99f6e4;border-radius:12px;padding:11px;margin:10px 0 14px;background:#f0fdfa;color:#134e4a;}
.remove-bg-tool b,.remove-bg-tool small{display:block;}
.remove-bg-tool small{font-size:11px;margin:4px 0 8px;color:#475569;line-height:1.5;}
.remove-bg-tool input{width:100%;font-size:10px;margin-bottom:8px;}
.remove-bg-tool img{max-width:100%;max-height:150px;display:block;object-fit:contain;background:repeating-conic-gradient(#e2e8f0 0 25%,#fff 0 50%) 50%/16px 16px;margin-bottom:8px;}
.topbar-game-logo{display:none;width:34px;height:34px;border-radius:8px;object-fit:contain;background:#f1f5f9;border:1px solid #d8e0ea;margin-right:4px;}
.header-left .topbar-game-logo.visible{display:block;}
</style>
</head>
<body>

<div class="app-container" id="app-container">

<!-- LOADING OVERLAY -->
<div id="loading-overlay">
  <div class="cyan-spinner">
    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
  </div>
  <div class="loading-text">LOADING</div>
</div>

<div class="sound-toggle" id="sound-toggle" onclick="toggleSound()">
  <i class="fa-solid fa-volume-high"></i>
</div>

<!-- AUTH -->
<div id="auth-section">
  <div class="auth-container">
    <div class="auth-logo-top">
      <img src="https://i.ibb.co/23xL2PYd/Gates-of-Olympus.png" id="auth-logo-img" alt="GAG2026" style="display:none;">
      <span id="auth-logo-text">GAG2026</span>
    </div>
    <div class="auth-card">
      <div id="login-page">
        <div class="auth-subtitle">Welcome Back</div>
        <div class="auth-title">ပြန်လည်ကြိုဆိုပါတယ်</div>
        <div class="auth-desc">ဖုန်းနံပါတ်ဖြင့် ဝင်ရောက်ပါ။</div>
        <div id="login-error-box" class="auth-error"></div>
        <div class="auth-input-group">
          <label>ဖုန်းနံပါတ်</label>
          <div class="input-wrapper">
            <div class="input-prefix">🇲🇲 +95</div>
            <input type="text" id="login-id" class="auth-input" placeholder="9xxxxxxxxx" autocomplete="off">
          </div>
        </div>
        <div class="auth-input-group">
          <label>စကားဝှက်</label>
          <div class="input-wrapper">
            <input type="password" id="login-pass" class="auth-input" placeholder="စကားဝှက်">
            <i class="fa-solid fa-eye-slash toggle-pass" onclick="togglePass('login-pass',this)"></i>
          </div>
        </div>
        <div class="auth-checkbox">
          <input type="checkbox" id="login-agree" checked>
          <label for="login-agree">ကျွန်ုပ်သည် အသက် 18 နှစ်ပြည့်ပြီးဖြစ်ကြောင်း သဘောတူပါသည်။</label>
        </div>
        <button class="auth-btn" id="login-btn" onclick="handleLogin()">ဝင်ရောက်မည်</button>
        <div class="auth-link">အကောင့်မရှိသေးပါသလား? <span onclick="switchAuth('register')">မှတ်ပုံတင်ရန်</span></div>
      </div>

      <div id="register-page" style="display:none;">
        <div class="auth-subtitle">Create Account</div>
        <div class="auth-title">အကောင့်ဖန်တီးပါ</div>
        <div class="auth-desc">ဖုန်းနံပါတ်ဖြင့် အကောင့်ဖွင့်ပါ။</div>
        <div id="reg-error-box" class="auth-error"></div>
        <div class="auth-input-group">
          <label>အသုံးပြုသူအမည်</label>
          <div class="input-wrapper"><input type="text" id="reg-name" class="auth-input" placeholder="သင့်အမည်"></div>
        </div>
        <div class="auth-input-group">
          <label>ဖုန်းနံပါတ်</label>
          <div class="input-wrapper">
            <div class="input-prefix">🇲🇲 +95</div>
            <input type="text" id="reg-contact" class="auth-input" placeholder="9xxxxxxxxx" autocomplete="off">
          </div>
        </div>
        <div class="auth-input-group">
          <label>စကားဝှက်</label>
          <div class="input-wrapper">
            <input type="password" id="reg-pass" class="auth-input" placeholder="စကားဝှက်">
            <i class="fa-solid fa-eye-slash toggle-pass" onclick="togglePass('reg-pass',this)"></i>
          </div>
        </div>
        <div class="auth-input-group">
          <label>စကားဝှက် အတည်ပြု</label>
          <div class="input-wrapper">
            <input type="password" id="reg-confirm" class="auth-input" placeholder="စကားဝှက် အတည်ပြု">
            <i class="fa-solid fa-eye-slash toggle-pass" onclick="togglePass('reg-confirm',this)"></i>
          </div>
        </div>
        <div class="auth-input-group">
          <label>Referral ကုဒ် (မလိုအပ်)</label>
          <div class="input-wrapper"><input type="text" id="reg-referral" class="auth-input" placeholder="Referral ကုဒ်"></div>
        </div>
        <div class="auth-checkbox">
          <input type="checkbox" id="reg-agree" checked>
          <label for="reg-agree">ကျွန်ုပ်သည် အသက် 18 နှစ်ပြည့်ပြီးဖြစ်ကြောင်း သဘောတူပါသည်။</label>
        </div>
        <button class="auth-btn" id="reg-btn" onclick="handleRegister()">အကောင့်ဖန်တီးမည်</button>
        <div class="auth-link">အကောင့်ရှိပြီးသားလား? <span onclick="switchAuth('login')">ဝင်ရောက်ရန်</span></div>
      </div>
    </div>
  </div>
</div>

<!-- MAIN APP -->
<div id="app-content">
  <div id="support-fab" class="floating-cs-btn" onclick="openSupport()">
    <i class="fa-solid fa-headset" style="font-size:28px;color:#fff;"></i>
  </div>

  <div id="sidebar-overlay" class="sidebar-overlay" onclick="toggleSidebar()"></div>
  <div id="sidebar" class="sidebar">
    <div class="sidebar-header-section">
      <div class="sidebar-avatar">U</div>
      <div>
        <h4 id="sidebar-name" style="font-size:15px;">User</h4>
        <p id="sidebar-id" style="font-size:12px;color:#a8a4b8;">UID: ---</p>
      </div>
    </div>
    <ul class="sidebar-menu">
      <li onclick="showPage('home',document.getElementById('nav-home'));toggleSidebar();"><i class="fa-solid fa-house"></i> ပင်မစာမျက်နှာ</li>
      <li onclick="showPage('refer',document.querySelectorAll('.nav-item')[1]);toggleSidebar();"><i class="fa-solid fa-share-nodes"></i> မိတ်ဆက်</li>
      <li onclick="showPage('bonus-page',document.querySelectorAll('.nav-item')[2]);toggleSidebar();"><i class="fa-solid fa-gift"></i> ဘောနပ်စ်</li>
      <li onclick="showPage('wallet',document.querySelectorAll('.nav-item')[3]);toggleSidebar();"><i class="fa-solid fa-wallet"></i> ပိုက်ဆံအိတ်</li>
      <li onclick="showPage('history',document.querySelectorAll('.nav-item')[4]);toggleSidebar();"><i class="fa-solid fa-clock-rotate-left"></i> မှတ်တမ်း</li>
      <li onclick="showPage('rules-page',null);toggleSidebar();"><i class="fa-solid fa-circle-info"></i> စည်းမျဉ်းများ</li>
      <li onclick="openSupport()"><i class="fa-solid fa-headset"></i> ဝန်ဆောင်မှု</li>
    </ul>
    <div class="sidebar-footer">
      <button class="logout-btn-sidebar" onclick="logoutApp()"><i class="fa-solid fa-power-off"></i> ထွက်မည်</button>
    </div>
  </div>

  <header id="main-header">
    <div class="header-left">
      <i class="fa-solid fa-bars menu-btn" onclick="toggleSidebar()"></i>
      <img id="topbar-game-logo" class="topbar-game-logo" alt="Game logo">
      <span class="user-greeting" id="header-greeting">မင်္ဂလာပါ</span>
    </div>
    <div class="header-right">
      <i class="fa-solid fa-bell bell-icon" onclick="showPage('notifications-page',null)">
        <span id="notif-badge" class="notif-badge">0</span>
      </i>
      <div class="header-wallet-btn" onclick="showPage('wallet',document.querySelectorAll('.nav-item')[3])">
        <i class="fa-solid fa-wallet"></i> Ks <span id="displayBalance">0</span>
      </div>
    </div>
  </header>

  <!-- HOME -->
  <div id="home" class="page active">
    <!-- SLIDER BOARD (Play Game Board ကို ဖျက်၊ ဒါကို ထည့်) -->
    <div class="slider-board" id="slider-board">
      <div class="slider-track" id="slider-track">
        <div class="slider-slide" style="background-image:url('https://i.ibb.co/23xL2PYd/Gates-of-Olympus.png');">
          <div class="slider-content">
            <div class="slider-title">GAG2026</div>
            <div class="slider-sub">ကစားပြီး ဆုလာဘ်များ ရယူပါ</div>
            <button class="slider-btn" onclick="openWingoGame()">
              <i class="fa-solid fa-play"></i> PLAY NOW
            </button>
          </div>
        </div>
      </div>
      <div class="slider-dots" id="slider-dots"></div>
    </div>

    <div class="stats-row">
      <div class="stat-box"><span>အနိုင်ရပိုက်ဆံအိတ်</span><h2 class="text-green-stat" id="statWinning">0</h2></div>
      <div class="stat-box"><span>ဘောနပ်စ်</span><h2 class="text-blue-stat" id="statBonus">0</h2></div>
    </div>

    <div class="leaderboard-section">
      <div class="lb-header">
        <h3><i class="fa-solid fa-trophy"></i> အနိုင်ရသူများ</h3>
        <span style="font-size:10px;color:#00e676;"><i class="fa-solid fa-circle" style="font-size:6px;"></i> LIVE</span>
      </div>
      <div class="lb-list" id="lb-list"></div>
    </div>

    <div id="african-buffalo-real-section">
      <div class="section-title">
        <i class="fa-solid fa-buffalo"></i> African Buffalo · Real Game
        <span class="provider-badge">4 ROOMS</span>
      </div>
      <div id="african-buffalo-real-games" class="game-grid"></div>
    </div>

    <div id="wingo-section">
      <div class="section-title">
        <i class="fa-solid fa-circle-half-stroke"></i> ကစားနိုင်သော ဂိမ်းများ
      </div>
      <div class="wingo-big-card" onclick="openWingoGame()">
        <div class="wingo-logo-wrap" id="wingo-logo-wrap">
          <i class="fa-solid fa-circle-half-stroke default-wingo-icon"></i>
        </div>
        <div class="wingo-info">
          <h3>WINGO</h3>
          <p>30s · 1m · 3m · 5m</p>
        </div>
        <button class="wingo-play-btn">PLAY</button>
      </div>
    </div>

    <div id="demo-games-container"></div>
  </div>

  <!-- REFER -->
  <div id="refer" class="page">
    <h2 style="margin-bottom:20px;">မိတ်ဆက်ရင်းနှီးမြှုပ်နှံ</h2>
    <div class="refer-card">
      <i class="fa-solid fa-ribbon refer-icon"></i>
      <p class="step-text"><b>အဆင့် ၁:</b> သင့် Referral လင့်ခ်ကို မျှဝေပါ</p>
      <p class="step-text"><b>အဆင့် ၂:</b> သူငယ်ချင်း အကောင့်ဖွင့်ပြီး ငွေသွင်းပါ</p>
      <span class="step-green">အဆင့် ၃: သင် ဘောနပ်စ် ရမည်!</span>
      <div class="refer-code-box" onclick="copyToClipboard(document.getElementById('displayReferCode').innerText)">
        <span id="displayReferCode">LOADING...</span> <i class="fa-regular fa-copy" style="font-size:16px;margin-left:10px;"></i>
      </div>
      <button class="share-btn-lg" onclick="nativeShare()"><i class="fa-brands fa-whatsapp"></i> WhatsApp မှ မျှဝေမည်</button>
    </div>
  </div>

  <!-- WALLET -->
  <div id="wallet" class="page">
    <h2 style="margin-bottom:20px;">ပိုက်ဆံအိတ်</h2>
    <div id="turnover-board" class="turnover-board">
      <div class="turnover-board-title">Turnover Progress</div>
      <div class="turnover-row"><span>Deposit turnover</span><b id="deposit-turnover-text">0 / 0 Ks</b></div>
      <div class="turnover-track"><span id="deposit-turnover-bar"></span></div>
      <div class="turnover-row"><span>Bonus turnover</span><b id="bonus-turnover-text">0 / 0 Ks</b></div>
      <div class="turnover-track"><span id="bonus-turnover-bar"></span></div>
      <div id="turnover-remaining" class="turnover-remaining">ငွေထုတ်ရန် turnover စစ်ဆေးနေပါတယ်...</div>
    </div>
    <div id="member-bonus-card" style="display:none;background:#fff;border:1px solid #111827;border-radius:12px;padding:14px;margin-bottom:16px;box-shadow:0 5px 14px rgba(15,23,42,.10);color:#172033;">
      <b>Member Welcome Bonus</b><br><small>10,000 Ks သွင်းပြီးနောက် 10,000 Ks claim လုပ်နိုင်ပါတယ်။ Claim လုပ်ပြီး 120,000 Ks ကစားပြီးမှ ငွေထုတ်နိုင်ပါမယ်။</small>
      <button id="member-bonus-claim-btn" class="btn-primary" style="margin-top:10px;" onclick="claimMemberBonus()">Claim 10,000 Ks</button>
    </div>
    <div class="w-tab-container">
      <button class="w-tab-btn active" onclick="showWalletTab('deposit',this)">ငွေသွင်း</button>
      <button class="w-tab-btn" onclick="showWalletTab('withdraw',this)">ငွေထုတ်</button>
    </div>

    <div id="w-deposit-section" class="w-content-box active">
      <div style="margin-bottom:15px;font-size:13px;color:#a8a4b8;"><i class="fa-solid fa-circle-info"></i> ငွေသွင်းမည့်နည်းလမ်းကို ရွေးပါ</div>
      <div class="pay-method-tabs">
        <div class="pay-method-btn active" onclick="selectPayMethod('kpay',this)">
          <div class="pm-logo" id="kpay-logo-display">KPay</div>
          <div class="pm-name">KPay</div>
        </div>
        <div class="pay-method-btn" onclick="selectPayMethod('wave',this)">
          <div class="pm-logo" id="wave-logo-display">Wave</div>
          <div class="pm-name">Wave Pay</div>
        </div>
      </div>

      <div style="background:rgba(255,193,7,0.1);border-left:4px solid #ffc107;padding:12px;border-radius:10px;margin-bottom:15px;font-size:12px;color:#fcd34d;">
        <i class="fa-solid fa-clock"></i> <b>Manual</b> — Admin အတည်ပြုမှ ငွေဝင်ပါမယ်။
      </div>

      <div class="pay-info-box">
        <div class="pay-info-row">
          <span class="pay-info-label">ဖုန်းနံပါတ်</span>
          <div class="pay-info-value-wrap">
            <span class="pay-info-value" id="dep-phone">-</span>
            <button class="copy-btn" onclick="copyPhone()"><i class="fa-regular fa-copy"></i></button>
          </div>
        </div>
        <div class="pay-info-row">
          <span class="pay-info-label">အကောင့်အမည်</span>
          <span class="pay-info-value" id="dep-name">-</span>
        </div>
      </div>
      <div class="amount-grid">
        <div class="amt-chip" onclick="fillDepAmt(1000)">1,000</div>
        <div class="amt-chip" onclick="fillDepAmt(5000)">5,000</div>
        <div class="amt-chip" onclick="fillDepAmt(10000)">10,000</div>
        <div class="amt-chip" onclick="fillDepAmt(20000)">20,000</div>
        <div class="amt-chip" onclick="fillDepAmt(50000)">50,000</div>
        <div class="amt-chip" onclick="fillDepAmt(100000)">100,000</div>
      </div>
      <div class="input-group-bonus">
        <label>ငွေပမာဏ (Ks)</label>
        <input type="number" id="depAmount" class="bonus-input" placeholder="အနည်းဆုံး 1,000 Ks">
      </div>
      <div class="divider"></div>
      <div class="input-group-bonus">
        <label>Transaction ID</label>
        <input type="text" id="utrInput" class="bonus-input" placeholder="လွှဲပြီးရရှိသည့် ID ကို ထည့်ပါ">
      </div>
      <div class="info-txt"><i class="fa-solid fa-circle-info"></i> ငွေလွှဲပြီး Transaction ID ထည့်ပါ။ Admin အတည်ပြုမှ ငွေဝင်ပါမယ်။</div>
      <button class="btn-submit-utr" id="depositBtn" onclick="processDeposit(event)"><i class="fa-solid fa-paper-plane"></i> တင်ပြမည်</button>
    </div>

    <div id="w-withdraw-section" class="w-content-box">
      <div class="balance-card-mini">
        <div>
          <span style="font-size:12px;color:#a8a4b8;">ရရှိနိုင်သော လက်ကျန်ငွေ</span>
          <h2 id="with-bal-display">Ks 0</h2>
        </div>
        <i class="fa-solid fa-wallet" style="font-size:30px;color:var(--gold);opacity:0.5;"></i>
      </div>
      <div style="margin-bottom:15px;font-size:13px;color:#a8a4b8;"><i class="fa-solid fa-circle-info"></i> ငွေထုတ်မည့်နည်းလမ်းကို ရွေးပါ</div>
      <div class="pay-method-tabs">
        <div class="pay-method-btn active" onclick="selectWithdrawMethod('kpay',this)">
          <div class="pm-logo" id="kpay-logo-display-w">KPay</div>
          <div class="pm-name">KPay</div>
        </div>
        <div class="pay-method-btn" onclick="selectWithdrawMethod('wave',this)">
          <div class="pm-logo" id="wave-logo-display-w">Wave</div>
          <div class="pm-name">Wave Pay</div>
        </div>
      </div>
      <div class="input-group-bonus"><label>ဖုန်းနံပါတ်</label><input type="text" id="withdrawPhone" class="bonus-input" placeholder="09xxxxxxxxx"></div>
      <div class="input-group-bonus"><label>အကောင့်အမည်</label><input type="text" id="withdrawName" class="bonus-input" placeholder="အကောင့်ပိုင်ရှင်အမည်"></div>
      <div class="input-group-bonus"><label>ငွေထုတ်ပမာဏ (Ks)</label><input type="number" id="withAmount" class="bonus-input" placeholder="အနည်းဆုံး 10,000 Ks"></div>
      <div class="input-group-bonus"><label>စကားဝှက်</label><input type="password" id="with-password" class="bonus-input" placeholder="သင့်စကားဝှက်"></div>
      <button class="bonus-btn-lg" style="background:linear-gradient(90deg,#ea5455,#c0392b);" onclick="handleWithdraw()"><i class="fa-solid fa-money-bill-transfer"></i> ငွေထုတ်မည်</button>
    </div>
  </div>

  <!-- HISTORY -->
  <div id="history" class="page">
    <h2 style="margin-bottom:20px;">ငွေလုပ်ငန်းမှတ်တမ်း</h2>
    <div id="historyList" style="padding:10px;"></div>
  </div>

  <!-- BONUS -->
  <div id="bonus-page" class="page">
    <h2 style="margin-bottom:20px;">ဘောနပ်စ် & ဆုလာဘ်</h2>
    <div id="member-bonus-card-bonus-page" class="member-bonus-page-card" style="display:none;">
      <b>10,000 Ks Member Welcome Bonus</b>
      <p>10,000 Ks deposit အတည်ပြုပြီးပါက 10,000 Ks ကို claim လုပ်နိုင်ပါတယ်။ Claim ပြီးရင် 120,000 Ks turnover လိုအပ်ပါတယ်။</p>
      <button id="member-bonus-claim-btn-bonus-page" class="btn-primary" onclick="claimMemberBonus()">Claim 10,000 Ks</button>
    </div>
    <div id="bonus-locked-notice" style="background:rgba(239,68,68,0.12);border-left:4px solid #ef4444;padding:15px;border-radius:10px;margin-bottom:15px;font-size:13px;color:#fca5a5;display:none;">
      <i class="fa-solid fa-lock"></i> <b>ငွေသွင်းပြီးမှ ရယူနိုင်ပါမယ်</b><br>
      <span style="font-size:12px;opacity:0.85;">Wallet မှာ ငွေသွင်းပြီးမှ Gift Code ရယူလို့ရပါမယ်။</span>
    </div>
    <div class="bonus-gift-card">
      <div class="gift-icon-container"><i class="fa-solid fa-gift"></i></div>
      <p class="bonus-instruction">Gift ကုဒ်ထည့်ပြီး ဘောနပ်စ်ပိုက်ဆံအိတ်ထဲ ရယူပါ</p>
      <div class="input-group-bonus">
        <label>Gift ကုဒ်</label>
        <input type="text" id="giftCodeInput" class="bonus-input" placeholder="ကုဒ်ကို ဒီမှာထည့်ပါ">
      </div>
      <button class="bonus-btn-lg" id="bonus-redeem-btn" onclick="redeemGiftCode()"><i class="fa-solid fa-gift"></i> ဘောနပ်စ်ရယူမည်</button>
    </div>
    <div style="margin-top:20px;">
      <h4 style="margin-bottom:15px;font-size:14px;color:#a8a4b8;">ဘောနပ်စ်မှတ်တမ်း</h4>
      <div id="bonus-history-list" style="display:flex;flex-direction:column;gap:10px;"></div>
    </div>
  </div>

  <!-- RULES -->
  <div id="rules-page" class="page">
    <h2 style="margin-bottom:20px;">ငွေသွင်း / ငွေထုတ် စည်းမျဉ်းများ</h2>
    <div id="rules-custom-text" class="rules-card" style="display:none;white-space:pre-wrap;"></div>
    <div class="rules-card"><h3>ငွေသွင်းခြင်း</h3><p>• အနည်းဆုံးငွေသွင်းပမာဏကို Wallet စာမျက်နှာမှာ ပြထားတဲ့အတိုင်း လိုက်နာပါ။</p><p>• Admin အတည်ပြုပြီးမှသာ ကစားနိုင်တဲ့ wallet ထဲ ငွေဝင်ပါမယ်။</p><p>• နောက်ထပ်ငွေသွင်းရန် အရင် deposit ပမာဏအတိုင်း <b>1× turnover</b> ကစားပြီးရပါမယ်။</p></div>
    <div class="rules-card"><h3>ငွေထုတ်ခြင်း</h3><p>• အနည်းဆုံးငွေထုတ်ပမာဏမှာ <b>10,000 Ks</b> ဖြစ်ပါတယ်။</p><p>• Deposit turnover မပြည့်သေးပါက withdrawal request တင်လို့မရပါ။</p><p>• Bonus claim လုပ်ထားပါက bonus turnover ပြည့်ပြီးမှသာ withdrawal ရပါမယ်။</p></div>
    <div class="rules-card"><h3>Bonus နှင့် Loss-back</h3><p>• Member welcome bonus ကို သတ်မှတ်ချက်ပြည့်တဲ့ account အသစ်များသာ claim လုပ်နိုင်ပါတယ်။</p><p>• Bonus claim လုပ်ပြီးပါက bonus amount ရဲ့ 12× turnover လိုအပ်ပါတယ်။</p><p>• နေ့စဉ် loss-back ရှိပါက Myanmar time 2:30 PM နောက်ပိုင်း စာရင်းရှင်းပြီး winning wallet ထဲ ပြန်ထည့်ပေးပါတယ်။</p></div>
    <div class="rules-card rules-safe"><h3>Responsible Play</h3><p>အသက် 18 နှစ်နှင့်အထက် အသုံးပြုသူများအတွက်သာ ဖြစ်ပါတယ်။ ဆုံးရှုံးနိုင်သည့်ပမာဏထက် မပိုဘဲ ကစားပါ။</p></div>
  </div>

  <!-- NOTIFICATIONS -->
  <div id="notifications-page" class="page">
    <h2 style="margin-bottom:20px;display:flex;align-items:center;gap:10px;">
      <i class="fa-solid fa-arrow-left" onclick="showPage('home',document.getElementById('nav-home'))" style="cursor:pointer;"></i> အသိပေးချက်များ
    </h2>
    <div id="notifications-list" style="padding:10px;"></div>
  </div>

  <div class="navbar" id="main-navbar">
    <button id="nav-home" class="nav-item active" onclick="showPage('home',this)"><i class="fa-solid fa-house"></i><span>ပင်မ</span></button>
    <button class="nav-item" onclick="showPage('refer',this)"><i class="fa-solid fa-share-nodes"></i><span>မိတ်ဆက်</span></button>
    <button class="nav-item" onclick="showPage('bonus-page',this)"><i class="fa-solid fa-gift"></i><span>ဘောနပ်စ်</span></button>
    <button class="nav-item" onclick="showPage('wallet',this)"><i class="fa-solid fa-wallet"></i><span>အိတ်</span></button>
    <button class="nav-item" onclick="showPage('history',this)"><i class="fa-solid fa-clock-rotate-left"></i><span>မှတ်တမ်း</span></button>
    <button class="nav-item" onclick="showPage('rules-page',this)"><i class="fa-solid fa-circle-info"></i><span>စည်းမျဉ်း</span></button>
  </div>
</div>

<!-- DEMO GAME OVERLAY -->
<div id="demo-game-overlay">
  <div class="demo-header">
    <div class="title" id="demo-game-title">Demo Game</div>
    <button class="close-btn" onclick="closeDemoGame()"><i class="fa-solid fa-xmark"></i></button>
  </div>
  <iframe id="demo-game-frame" src="about:blank" allow="fullscreen; autoplay"></iframe>
</div>

<!-- WINGO GAME -->
<div id="wingo-game-container">
  <div class="wingo-header">
    <div class="header-icon" onclick="closeWingoGame()"><i class="fas fa-chevron-left"></i></div>
    <div class="header-title" id="wingo-title">GAG2026 <span style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:1px;color:#00e676;border:1px solid #00e676;border-radius:10px;padding:3px 7px;vertical-align:middle;">REAL GAME</span></div>
    <div class="header-icon" id="wingo-sound-btn" onclick="toggleSound()"><i class="fas fa-volume-high"></i></div>
  </div>
  <div class="wallet-section">
    <div class="wallet-bal-label"><i class="fas fa-wallet"></i> ပိုက်ဆံအိတ် လက်ကျန်</div>
    <div class="wallet-amount">Ks <span id="w-balance">0</span></div>
    <div class="wallet-btns">
      <button class="w-btn w-btn-withdraw" onclick="closeWingoGame();showPage('wallet',document.querySelectorAll('.nav-item')[3])"><i class="fas fa-arrow-up"></i> ငွေထုတ်</button>
      <button class="w-btn w-btn-deposit" onclick="closeWingoGame();showPage('wallet',document.querySelectorAll('.nav-item')[3])"><i class="fas fa-arrow-down"></i> ငွေသွင်း</button>
    </div>
  </div>
  <div class="notice-bar">
    <i class="fas fa-bullhorn"></i>
    <marquee scrollamount="4">အရေးကြီးအသိပေးချက်: ကျွန်ုပ်တို့၏ ဝန်ဆောင်မှုအဖွဲ့သည် အဖွဲ့ဝင်များကို မည်သည့်လင့်ခ်ကိုမျှ ပေးပို့မည်မဟုတ်ပါ။</marquee>
  </div>
  <div class="time-tabs">
    <div class="time-tab active" onclick="switchTime(30,this)"><i class="far fa-clock clock-icon"></i><span class="tab-text">WinGo<br>30s</span></div>
    <div class="time-tab" onclick="switchTime(60,this)"><i class="far fa-clock clock-icon"></i><span class="tab-text">WinGo<br>1m</span></div>
    <div class="time-tab" onclick="switchTime(180,this)"><i class="far fa-clock clock-icon"></i><span class="tab-text">WinGo<br>3m</span></div>
    <div class="time-tab" onclick="switchTime(300,this)"><i class="far fa-clock clock-icon"></i><span class="tab-text">WinGo<br>5m</span></div>
  </div>
  <div class="timer-card">
    <div class="timer-left">
      <div class="how-to-play-btn"><i class="fas fa-file-alt"></i> ကစားနည်း</div>
      <div class="period-txt">WinGo <span id="curr-time-disp">30s</span></div>
      <div class="period-num" id="period-display">ဖွင့်နေသည်...</div>
    </div>
    <div class="timer-right">
      <div class="time-rem-txt">ကျန်ရှိချိန်</div>
      <div class="countdown-box">
        <div class="c-box">0</div><div class="c-box">0</div>
        <span style="color:#FFD700;font-weight:bold;font-size:20px;">:</span>
        <div class="c-box" id="min">00</div><div class="c-box" id="sec">00</div>
      </div>
    </div>
  </div>
  <div class="game-area" id="game-area">
    <div class="countdown-overlay-box" id="countdown-overlay">
      <div class="cd-card" id="cd-1">0</div>
      <div class="cd-card" id="cd-2">5</div>
    </div>
    <div class="color-btns">
      <button class="c-btn btn-g" onclick="openBet('Green')">အစိမ်း</button>
      <button class="c-btn btn-v" onclick="openBet('Violet')">ခရမ်း</button>
      <button class="c-btn btn-r" onclick="openBet('Red')">အနီ</button>
    </div>
    <div class="number-grid">
      <button class="num-btn n0" onclick="openBet('0')">0</button>
      <button class="num-btn n1" onclick="openBet('1')">1</button>
      <button class="num-btn n2" onclick="openBet('2')">2</button>
      <button class="num-btn n3" onclick="openBet('3')">3</button>
      <button class="num-btn n4" onclick="openBet('4')">4</button>
      <button class="num-btn n5" onclick="openBet('5')">5</button>
      <button class="num-btn n6" onclick="openBet('6')">6</button>
      <button class="num-btn n7" onclick="openBet('7')">7</button>
      <button class="num-btn n8" onclick="openBet('8')">8</button>
      <button class="num-btn n9" onclick="openBet('9')">9</button>
    </div>
    <div class="bs-btns">
      <button class="bs-btn btn-big" onclick="openBet('Big')">ကြီး</button>
      <button class="bs-btn btn-small" onclick="openBet('Small')">သေး</button>
    </div>
  </div>
  <div class="records-container">
    <div class="r-tabs">
      <div class="r-tab active" onclick="showTab('history',this)">ဂိမ်းမှတ်တမ်း</div>
      <div class="r-tab" onclick="showTab('chart',this)">ဇယား</div>
      <div class="r-tab" onclick="showTab('mybet',this)">ကျွန်ုပ်၏မှတ်တမ်း</div>
    </div>
    <div id="history-content" style="display:block;">
      <table class="gh-table">
        <thead><tr><th>ကာလ</th><th>နံပါတ်</th><th>ကြီး/သေး</th><th>အရောင်</th></tr></thead>
        <tbody id="gh-body"></tbody>
      </table>
      <div class="pagination-box">
        <button class="pg-btn" onclick="changePage(-1)"><i class="fas fa-chevron-left"></i></button>
        <div class="pg-info" id="page-info">1/50</div>
        <button class="pg-btn" onclick="changePage(1)"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    <div id="chart-content" style="display:none;">
      <div class="chart-header-row"><div class="ch-period">ကာလ</div><div class="ch-number">နံပါတ်</div></div>
      <div class="chart-scroll" id="chart-scroll-area">
        <svg class="chart-svg" id="chart-svg"></svg>
        <div id="chart-rows"></div>
      </div>
    </div>
    <div id="mybet-content" style="display:none;padding:10px;">
      <div id="my-bets-list"></div>
      <div class="pagination-box" id="my-bet-pagination" style="display:flex;margin-top:10px;">
        <button class="pg-btn" onclick="changeMyBetPage(-1)"><i class="fas fa-chevron-left"></i></button>
        <div class="pg-info" id="my-bet-page-info">1/1</div>
        <button class="pg-btn" onclick="changeMyBetPage(1)"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
  </div>
</div>

<!-- BET SHEET -->
<div class="bet-overlay" id="bet-overlay" onclick="closeBet()"></div>
<div class="bet-sheet" id="bet-sheet">
  <div class="bs-head">
    WinGo <span id="bs-time">30s</span><br>
    <div class="bs-select-display" id="bs-select-display">ရွေးပါ</div>
  </div>
  <div class="bs-body">
    <div class="bs-row" style="justify-content:space-between;">
      <span style="color:#FFD700;">လောင်းကြေး</span>
      <div style="display:flex;gap:5px;flex-wrap:wrap;">
        <button class="money-btn active" onclick="setAmt(100)">100</button>
        <button class="money-btn" onclick="setAmt(500)">500</button>
        <button class="money-btn" onclick="setAmt(1000)">1K</button>
        <button class="money-btn" onclick="setAmt(5000)">5K</button>
      </div>
    </div>
    <div class="bs-row" style="justify-content:space-between;">
      <span style="color:#FFD700;">အရေအတွက်</span>
      <div class="qty-box">
        <button class="qty-btn" onclick="addQty(-1)">-</button>
        <div class="qty-val" id="qty-display">1</div>
        <button class="qty-btn" onclick="addQty(1)">+</button>
      </div>
    </div>
    <div class="bs-row" style="flex-wrap:wrap;">
      <button class="money-btn active" onclick="setMul(1)">X1</button>
      <button class="money-btn" onclick="setMul(5)">X5</button>
      <button class="money-btn" onclick="setMul(10)">X10</button>
      <button class="money-btn" onclick="setMul(20)">X20</button>
      <button class="money-btn" onclick="setMul(50)">X50</button>
      <button class="money-btn" onclick="setMul(100)">X100</button>
    </div>
  </div>
  <div class="bs-foot">
    <button class="bs-cancel" onclick="closeBet()">မလုပ်တော့ပါ</button>
    <button class="bs-ok" onclick="placeBet()">စုစုပေါင်း Ks <span id="total-amt">100</span></button>
  </div>
</div>

<!-- WIN/LOSS -->
<div class="win-popup" id="win-popup">
  <div class="win-card">
    <div class="win-header-deco"></div>
    <div class="win-title">ဂုဏ်ယူပါတယ်!</div>
    <div class="win-res-row" id="win-res-row"></div>
    <div class="win-bonus-box">
      <span class="win-label-bonus">ဘောနပ်စ်</span>
      <span class="win-amount" id="win-amount">Ks 0</span>
    </div>
    <div class="win-close-timer"><i class="far fa-check-circle"></i> 3 စက္ကန့်အကြာ အလိုအလျောက်ပိတ်မည်</div>
  </div>
</div>
<div class="popup-loss" id="loss-popup">
  <div class="loss-card">
    <i class="fas fa-frown" style="font-size:50px;color:#555;margin-bottom:15px;"></i>
    <div class="loss-title">စိတ်မကောင်းပါ</div>
    <div class="loss-res" id="loss-res-txt">ရလဒ်: -</div>
    <button class="loss-btn" onclick="closePopup()">ပိတ်မည်</button>
  </div>
</div>

<div id="toast">Message</div>
</div>

<script>
const API_BASE = window.location.origin;
let currentUser = null;
let gameInterval = null;
let currTime = 30;
let currentPage = 1;
let currentMyBetPage = 1;
let activeWingoBets = [];
let selectedBet = "";
let amt = 100, qty = 1, mul = 1;
let gameData = {30:{history:[],period:''},60:{history:[],period:''},180:{history:[],period:''},300:{history:[],period:''}};
let selectedDepositMethod = 'kpay';
let selectedWithdrawMethod = 'kpay';
let globalSettings = {};
let publicIconPack = {};
let demoGames = {};
let soundEnabled = true;
let sliderIndex = 0;
let sliderInterval = null;

function applyConfiguredIcons(pack){
  publicIconPack = pack || {};
  const replaceIcon = (el, src, key) => {
    if(!el || !src || el.tagName === 'IMG') return;
    const img = document.createElement('img');
    img.src = src; img.alt = key || 'icon';
    img.className = Array.from(el.classList).filter(c => !c.startsWith('fa') && !['fas','far','fab','icon-image'].includes(c)).concat(['icon-image-element']).join(' ');
    Array.from(el.attributes).forEach(attr=>{
      if(['class','style','aria-label'].includes(attr.name)) return;
      img.setAttribute(attr.name, attr.value);
    });
    if(el.getAttribute('style')) img.setAttribute('style', el.getAttribute('style'));
    el.replaceWith(img);
  };
  const selectors = {
    home: 'i.fa-house', wallet: 'i.fa-wallet', bonus: 'i.fa-gift',
    history: 'i.fa-clock-rotate-left', rules: 'i.fa-circle-info', support: 'i.fa-headset',
    menu: 'i.fa-bars', bell: 'i.fa-bell', deposit: 'i.fa-arrow-down, i.fa-money-bill-wave',
    withdraw: 'i.fa-arrow-up, i.fa-money-bill-transfer', close: 'i.fa-xmark',
    eye: 'i.fa-eye, i.fa-eye-slash', save: 'i.fa-save, i.fa-floppy-disk',
    check: 'i.fa-check', lock: 'i.fa-lock', arrowleft: 'i.fa-arrow-left'
  };
  Object.entries(selectors).forEach(([key, selector])=>{
    if(!publicIconPack[key]) return;
    document.querySelectorAll(selector).forEach(el=>{
      replaceIcon(el, publicIconPack[key], key);
    });
  });
  if(publicIconPack.generic){
    document.querySelectorAll('i[class*="fa-"]').forEach(el=>replaceIcon(el, publicIconPack.generic, 'generic'));
  }
}

// ============ SOUND ============
let audioCtx = null;
function initAudio(){
  if(!audioCtx){
    try{audioCtx = new (window.AudioContext || window.webkitAudioContext)();}catch(e){}
  }
}
function playSound(type){
  if(!soundEnabled) return;
  initAudio();
  if(!audioCtx) return;
  try{
    if(audioCtx.state === 'suspended') audioCtx.resume();
    const now = audioCtx.currentTime;
    if(type === 'bet'){
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain); gain.connect(audioCtx.destination);
      osc.frequency.value = 800; osc.type = 'sine';
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
      osc.start(now); osc.stop(now + 0.1);
    } else if(type === 'win'){
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.frequency.value = freq; osc.type = 'sine';
        gain.gain.setValueAtTime(0, now + i*0.1);
        gain.gain.linearRampToValueAtTime(0.15, now + i*0.1 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.01, now + i*0.1 + 0.3);
        osc.start(now + i*0.1); osc.stop(now + i*0.1 + 0.3);
      });
    } else if(type === 'lose'){
      [392, 329.63, 261.63].forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.frequency.value = freq; osc.type = 'sine';
        gain.gain.setValueAtTime(0, now + i*0.15);
        gain.gain.linearRampToValueAtTime(0.12, now + i*0.15 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.01, now + i*0.15 + 0.25);
        osc.start(now + i*0.15); osc.stop(now + i*0.15 + 0.25);
      });
    } else if(type === 'tick'){
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain); gain.connect(audioCtx.destination);
      osc.frequency.value = 1200; osc.type = 'square';
      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
      osc.start(now); osc.stop(now + 0.05);
    } else if(type === 'notification'){
      [880, 1174.66].forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.frequency.value = freq; osc.type = 'sine';
        gain.gain.setValueAtTime(0, now + i*0.15);
        gain.gain.linearRampToValueAtTime(0.15, now + i*0.15 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.01, now + i*0.15 + 0.2);
        osc.start(now + i*0.15); osc.stop(now + i*0.15 + 0.2);
      });
    }
  }catch(e){}
}
function toggleSound(){
  soundEnabled = !soundEnabled;
  document.querySelectorAll('#sound-toggle i, #wingo-sound-btn i').forEach(icon => {
    icon.className = soundEnabled ? 'fas fa-volume-high' : 'fas fa-volume-xmark';
  });
  document.getElementById('sound-toggle').classList.toggle('muted', !soundEnabled);
  if(soundEnabled) playSound('notification');
  showToast(soundEnabled ? 'Sound On' : 'Sound Off');
}

// ============ HELPERS ============
function fmt(n){return Number(n).toLocaleString('en-US');}
function showLoading(){document.getElementById('loading-overlay').classList.add('active');}
function hideLoading(){document.getElementById('loading-overlay').classList.remove('active');}
function showAuthError(boxId, msg){
  const box = document.getElementById(boxId);
  box.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i>' + msg;
  box.classList.add('show');
  setTimeout(()=>box.classList.remove('show'), 5000);
}
function hideAuthError(boxId){
  const box = document.getElementById(boxId);
  box.classList.remove('show');
  box.innerHTML = '';
}

// ============ SETTINGS ============
async function loadSettings(){
  try{
    const r = await fetch(`${API_BASE}/api/settings`);
    const d = await r.json();
    if(d.success){
      globalSettings = d;
      applyConfiguredIcons(d.icon_pack || {});
      const customRules = document.getElementById('rules-custom-text');
      if(customRules && d.rules_text){customRules.textContent = d.rules_text; customRules.style.display='block';}
      if(d.app_name){
        document.title = d.app_name + ' - gag game site';
        document.getElementById('auth-logo-text').innerText = d.app_name;
        const wingoTitle = document.getElementById('wingo-title');
        wingoTitle.innerText = d.app_name;
        wingoTitle.insertAdjacentHTML('beforeend',' <span style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:1px;color:#00e676;border:1px solid #00e676;border-radius:10px;padding:3px 7px;vertical-align:middle;">REAL GAME</span>');
      }
      if(d.app_logo){
        const li = document.getElementById('auth-logo-img');
        li.src = d.app_logo;
        li.style.display = 'block';
        document.getElementById('auth-logo-text').style.display = 'none';
        const topLogo = document.getElementById('topbar-game-logo');
        if(topLogo){ topLogo.src = d.app_logo; topLogo.classList.add('visible'); }
      }
      if(d.login_bg){
        document.getElementById('auth-section').style.backgroundImage = `url('${d.login_bg}')`;
      } else {
        document.getElementById('auth-section').style.backgroundImage = "url('https://img.freepik.com/free-vector/dark-purple-gradient-background_78370-2954.jpg')";
      }
      // PAGE BG
      if(d.page_bg && d.page_bg.trim() !== ''){
        document.documentElement.style.setProperty('--page-bg-img', `url('${d.page_bg}')`);
        document.body.classList.add('has-bg');
      } else {
        document.documentElement.style.setProperty('--page-bg-img', 'none');
        document.body.classList.remove('has-bg');
      }
      // WINGO GAME BG
      if(d.wingo_bg && d.wingo_bg.trim() !== ''){
        const wgc = document.getElementById('wingo-game-container');
        wgc.style.setProperty('--wingo-bg', `url('${d.wingo_bg}')`);
        wgc.classList.add('has-bg');
      }
      // INGAME BG (slider)
      if(d.ingame_bg){
        // Will apply to slider via JS
        window._ingameBg = d.ingame_bg;
      }
      // WINGO LOGO
      const wingoWrap = document.getElementById('wingo-logo-wrap');
      if(d.wingo_logo && d.wingo_logo.trim() !== ''){
        wingoWrap.innerHTML = `<img src="${d.wingo_logo}" alt="Wingo">`;
      } else {
        wingoWrap.innerHTML = '<i class="fa-solid fa-circle-half-stroke default-wingo-icon"></i>';
      }
      // PAYMENT LOGOS
      const kpayDepHtml = (d.kpay_logo && d.kpay_logo.trim() !== '') ? `<img src="${d.kpay_logo}" alt="KPay">` : 'KPay';
      const waveDepHtml = (d.wave_logo && d.wave_logo.trim() !== '') ? `<img src="${d.wave_logo}" alt="Wave">` : 'Wave';
      document.getElementById('kpay-logo-display').innerHTML = kpayDepHtml;
      document.getElementById('wave-logo-display').innerHTML = waveDepHtml;
      const kpayW = document.getElementById('kpay-logo-display-w');
      const waveW = document.getElementById('wave-logo-display-w');
      if(kpayW) kpayW.innerHTML = kpayDepHtml;
      if(waveW) waveW.innerHTML = waveDepHtml;
      
      // SLIDER
      loadSlider();
      
      updatePaymentInfo();
    }
  }catch(e){console.error('loadSettings error:',e);}
}

// ============ SLIDER ============
async function loadSlider(){
  try{
    const r = await fetch(`${API_BASE}/api/sliders-public`);
    const d = await r.json();
    const track = document.getElementById('slider-track');
    const dots = document.getElementById('slider-dots');
    let slides = [];
    
    if(d.success && d.sliders && d.sliders.length > 0){
      slides = d.sliders;
    } else {
      // default slides
      slides = [
        {image:'https://i.ibb.co/23xL2PYd/Gates-of-Olympus.png', title:'GAG2026', sub:'ကစားပြီး ဆုလာဘ်များ ရယူပါ'},
        {image:'https://i.ibb.co/q3br7FMz/Sweet-Bonanza.png', title:'PLAY & WIN', sub:'အခုပဲ ကစားကြည့်ပါ'},
        {image:'https://i.ibb.co/n8fn7MJz/Fortune-Gems.png', title:'WINGO GAME', sub:'30s · 1m · 3m · 5m'},
      ];
    }
    
    let html = '';
    let dotsHtml = '';
    slides.forEach((s, i) => {
      const title = s.title || 'GAG2026';
      const sub = s.sub || 'ကစားပြီး ဆုလာဘ်များ ရယူပါ';
      html += `<div class="slider-slide" style="background-image:url('${s.image}');">
        <div class="slider-content">
          <div class="slider-title">${title}</div>
          <div class="slider-sub">${sub}</div>
          <button class="slider-btn" onclick="openWingoGame()">
            <i class="fa-solid fa-play"></i> PLAY NOW
          </button>
        </div>
      </div>`;
      dotsHtml += `<div class="slider-dot ${i===0?'active':''}" onclick="goToSlide(${i})"></div>`;
    });
    track.innerHTML = html;
    dots.innerHTML = dotsHtml;
    
    // Auto slide
    if(sliderInterval) clearInterval(sliderInterval);
    if(slides.length > 1){
      sliderInterval = setInterval(() => {
        sliderIndex = (sliderIndex + 1) % slides.length;
        updateSlider();
      }, 4000);
    }
  }catch(e){console.error(e);}
}

function updateSlider(){
  const track = document.getElementById('slider-track');
  if(!track) return;
  const total = track.children.length;
  if(total === 0) return;
  track.style.transform = `translateX(-${sliderIndex * 100}%)`;
  document.querySelectorAll('.slider-dot').forEach((d, i) => {
    d.classList.toggle('active', i === sliderIndex);
  });
}

function goToSlide(i){
  sliderIndex = i;
  updateSlider();
  if(sliderInterval) clearInterval(sliderInterval);
  sliderInterval = setInterval(() => {
    const track = document.getElementById('slider-track');
    const total = track.children.length;
    sliderIndex = (sliderIndex + 1) % total;
    updateSlider();
  }, 4000);
}

async function loadDemoGames(){
  try{
    showLoading();
    const r = await fetch(`${API_BASE}/api/demo-games`);
    const d = await r.json();
    if(d.success){demoGames = d.games;renderDemoGames();}
    setTimeout(hideLoading, 800);
  }catch(e){console.error(e);hideLoading();}
}

function renderDemoGames(){
  const c = document.getElementById('demo-games-container');
  if(!c) return;
  renderAfricanBuffaloRealGames();
  let html = '';
  html += `<div class="section-title" style="margin-top:24px;">
      <i class="fa-solid fa-gamepad"></i> Demo Game များအပြင်းအပြေဆော့ရန်
      <span class="provider-badge">DEMO GAMES</span>
    </div>`;
  const order = ['Pragmatic','JILI','PG Soft','BGaming','Habanero'];
  order.forEach(provider=>{
    const games = demoGames[provider];
    if(games && games.length > 0){
      html += `<div class="section-title">
          <i class="fa-solid fa-gamepad"></i> ${provider}
          <span class="provider-badge">${games.length} GAMES</span>
        </div>
        <div class="game-grid">`;
      games.forEach(g=>{
        const badge = g.badge || '';
        let badgeHtml = '';
        if(badge === 'new'){
          badgeHtml = `<div class="game-badge new">NEW</div>`;
        } else if(badge === 'hot'){
          badgeHtml = `<div class="game-badge hot">HOT</div>
            <svg class="fire-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <radialGradient id="fireGrad" cx="50%" cy="70%" r="60%">
                  <stop offset="0%" stop-color="#FFEB3B"/>
                  <stop offset="40%" stop-color="#FF9800"/>
                  <stop offset="100%" stop-color="#F44336"/>
                </radialGradient>
              </defs>
              <path d="M12 2C12 2 8 6 8 10C8 11.5 8.5 12.5 9 13C8.5 12 8 10.5 9 9C10 11 12 11 12 13C12 15 11 16 11 17C11 18 12 19 12 19C12 19 13 18 13 17C13 16 12 15 12 13C12 11 14 11 15 9C16 10.5 15.5 12 15 13C15.5 12.5 16 11.5 16 10C16 6 12 2 12 2Z" fill="url(#fireGrad)"/>
            </svg>`;
        }
        const clickAction = g.internal === 'buffalo_room' ? `openAfricanBuffalo(${Number(g.room_id)||1})` : (g.internal ? `openAfricanBuffalo(1)` : `openDemoGame('${g.title.replace(/'/g,"\\'")}','${g.url}')`);
        const displayRtp = g.internal === 'buffalo_room' ? (91 + ((Number(g.room_id)||1) * 2) + Math.floor(Math.random() * 3)) : null;
        html += `<div class="game-card" onclick="${clickAction}">
            <div class="game-thumb">
              ${badgeHtml}
              <img src="${g.img}" alt="${g.title}" onerror="this.style.display='none'" loading="lazy">
            </div>
            <div class="game-name">${g.title}${g.internal === 'buffalo_room' ? `<small style="display:block;color:#00e5ff;font-size:10px;margin-top:4px;">RTP ${displayRtp}%</small>` : '<small style="display:block;color:#ffcc66;font-size:10px;margin-top:4px;">DEMO GAME</small>'}</div>
          </div>`;
      });
      html += `</div>`;
    }
  });
  c.innerHTML = html || '<div style="text-align:center;color:#666;padding:30px;">No games</div>';
}

function renderAfricanBuffaloRealGames(){
  const c = document.getElementById('african-buffalo-real-games');
  if(!c) return;
  const games = demoGames['African Buffalo'] || [];
  c.innerHTML = games.map(g=>{
    const room = Number(g.room_id) || 1;
    const displayRtp = 91 + (room * 2) + Math.floor(Math.random() * 3);
    return `<div class="game-card" onclick="openAfricanBuffalo(${room})">
      <div class="game-thumb" style="background:linear-gradient(135deg,#14283b,#161229);">
        <div class="game-badge new">REAL</div>
        <img src="${g.img}" alt="${g.title}" onerror="this.style.display='none'" loading="lazy">
      </div>
      <div class="game-name">African Buffalo · Room ${room}<small style="display:block;color:#00e5ff;font-size:10px;margin-top:4px;">RTP ${displayRtp}% · REAL GAME</small></div>
    </div>`;
  }).join('') || '<div style="text-align:center;color:#666;padding:30px;">African Buffalo rooms unavailable</div>';
}

async function openDemoGame(title,url){
  if(!currentUser){showToast("အရင်ဝင်ပါ");return;}
  const r = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
  const d = await r.json();
  if(d.success){
    const hasDeposit = (d.user.wallet?.deposit || 0) > 0 || d.user.hasDeposited === true;
    if(!hasDeposit){showToast("Demo ဂိမ်းများ ကစားရန် ငွေသွင်းရန် လိုအပ်ပါသည်");return;}
  }
  showLoading();
  document.getElementById('demo-game-title').innerText = title + " (Demo)";
  document.getElementById('demo-game-frame').src = url;
  document.getElementById('demo-game-overlay').classList.add('active');
  setTimeout(hideLoading, 1200);
}

function openAfricanBuffalo(roomId){
  if(!currentUser){showToast("အရင်ဝင်ပါ");return;}
  try{localStorage.setItem('af_demo_user', currentUser.uid);localStorage.setItem('af_demo_room', String(roomId || 1));}catch(e){}
  showLoading();
  document.getElementById('demo-game-title').innerText = `African Buffalo · Room ${roomId || 1}`;
  document.getElementById('demo-game-frame').src = '/african-buffalo/';
  document.getElementById('demo-game-overlay').classList.add('active');
  setTimeout(hideLoading, 900);
}

function closeDemoGame(){
  document.getElementById('demo-game-overlay').classList.remove('active');
  document.getElementById('demo-game-frame').src = 'about:blank';
  if(currentUser){
    fetch(`${API_BASE}/api/user/${currentUser.uid}`).then(r=>r.json()).then(d=>{
      if(d.success){currentUser=d.user;updateUI();}
    }).catch(()=>{});
  }
}

function copyPhone(){
  const phone = selectedDepositMethod === 'kpay' ? globalSettings.kpay_phone : globalSettings.wave_phone;
  if(phone){
    navigator.clipboard.writeText(phone);
    showToast("Copy: " + phone);
  }
}

async function checkLoginStatus(){
  const uid = localStorage.getItem('gag_uid');
  if(uid){
    try{
      const r = await fetch(`${API_BASE}/api/user/${uid}`);
      const d = await r.json();
      if(d.success){
        currentUser = d.user;
        document.getElementById('auth-section').style.display='none';
        document.getElementById('app-content').style.display='block';
        document.getElementById('support-fab').style.display='flex';
        const fn = (currentUser.name||'User').split(' ')[0];
        document.getElementById('header-greeting').innerText = "မင်္ဂလာပါ, " + fn;
        document.getElementById('sidebar-name').innerText = currentUser.name;
        document.getElementById('sidebar-id').innerText = "UID: " + currentUser.uid;
        document.getElementById('displayReferCode').innerText = currentUser.uid;
        updateUI();
        loadTransactionHistory();
        loadUserBetHistory();
        loadNotifications();
        loadBonusHistory();
        return;
      }
    }catch(e){console.error(e);}
    localStorage.removeItem('gag_uid');
  }
  document.getElementById('auth-section').style.display='flex';
  document.getElementById('app-content').style.display='none';
}

async function handleRegister(){
  hideAuthError('reg-error-box');
  const name = document.getElementById('reg-name').value.trim();
  const contact = document.getElementById('reg-contact').value.trim();
  const pass = document.getElementById('reg-pass').value;
  const cp = document.getElementById('reg-confirm').value;
  const ref = document.getElementById('reg-referral').value.trim();
  const agree = document.getElementById('reg-agree').checked;
  
  if(!name || !contact || !pass || !cp){showAuthError('reg-error-box','အားလုံးဖြည့်ပါ');return;}
  if(!agree){showAuthError('reg-error-box','စည်းကမ်းချက်များကို သဘောတူပါ');return;}
  if(pass !== cp){showAuthError('reg-error-box','စကားဝှက် မတူပါ');return;}
  if(contact.length < 7){showAuthError('reg-error-box','ဖုန်းနံပါတ် မှန်ကန်စွာထည့်ပါ');return;}
  
  const btn = document.getElementById('reg-btn');
  const origText = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ဖန်တီးနေပါတယ်...';
  btn.disabled = true;
  showLoading();
  
  try{
    const r = await fetch(`${API_BASE}/api/register`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name,contact,password:pass,refCode:ref})
    });
    const d = await r.json();
    if(d.success){
      localStorage.setItem('gag_uid',d.uid);
      playSound('notification');
      showToast(`Account created! ${fmt(d.bonus)} Ks bonus`);
      checkLoginStatus();
    } else {
      showAuthError('reg-error-box', d.message || 'Failed');
    }
  }catch(e){
    showAuthError('reg-error-box','Error: ' + e.message);
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
    hideLoading();
  }
}

async function handleLogin(){
  hideAuthError('login-error-box');
  const id = document.getElementById('login-id').value.trim();
  const pass = document.getElementById('login-pass').value;
  const agree = document.getElementById('login-agree').checked;
  
  if(!id || !pass){showAuthError('login-error-box','ဖုန်းနံပါတ်နဲ့ စကားဝှက် ဖြည့်ပါ');return;}
  if(!agree){showAuthError('login-error-box','စည်းကမ်းချက်များကို သဘောတူပါ');return;}
  
  const btn = document.getElementById('login-btn');
  const origText = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> စစ်ဆေးနေပါတယ်...';
  btn.disabled = true;
  showLoading();
  
  try{
    const r = await fetch(`${API_BASE}/api/login`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({contact:id, password:pass})
    });
    const d = await r.json();
    if(d.success){
      localStorage.setItem('gag_uid', d.uid);
      playSound('notification');
      showToast("Login successful!");
      checkLoginStatus();
    } else {
      showAuthError('login-error-box', d.message || 'Failed');
    }
  }catch(e){
    showAuthError('login-error-box','Error: ' + e.message);
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
    hideLoading();
  }
}

function logoutApp(){
  localStorage.removeItem('gag_uid');
  if(gameInterval){clearInterval(gameInterval);gameInterval=null;}
  location.reload();
}

function switchAuth(t){
  document.getElementById('login-page').style.display = t==='login'?'block':'none';
  document.getElementById('register-page').style.display = t==='register'?'block':'none';
  hideAuthError('login-error-box');
  hideAuthError('reg-error-box');
}

function togglePass(id,el){
  const inp = document.getElementById(id);
  if(inp.type==='password'){inp.type='text';el.classList.remove('fa-eye-slash');el.classList.add('fa-eye');}
  else{inp.type='password';el.classList.remove('fa-eye');el.classList.add('fa-eye-slash');}
}

function toggleSidebar(){
  document.getElementById('sidebar').classList.toggle('active');
  document.getElementById('sidebar-overlay').classList.toggle('active');
}

function showPage(id,btn){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(id==='notifications-page'){
    document.getElementById('notif-badge').style.display='none';
    localStorage.setItem('last_read_notification_time',Date.now());
  }
  if(id==='bonus-page'){
    loadBonusHistory();
    updateBonusLock();
  }
  updateUI();
  window.scrollTo({top:0,behavior:'smooth'});
}

function getPlayableBalance(){
  if(!currentUser) return 0;
  const w = currentUser.wallet || {};
  return (w.deposit||0) + (w.winning||0);
}

function updateUI(){
  const w = currentUser ? (currentUser.wallet || {}) : {};
  const playable = (w.deposit||0) + (w.winning||0);
  document.getElementById('displayBalance').innerText = fmt(playable);
  document.getElementById('w-balance').innerText = fmt(playable);
  document.getElementById('with-bal-display').innerText = "Ks " + fmt(playable);
  document.getElementById('statWinning').innerText = fmt(w.winning||0);
  document.getElementById('statBonus').innerText = fmt(w.bonus||0);
  const memberCard = document.getElementById('member-bonus-card');
  const memberBtn = document.getElementById('member-bonus-claim-btn');
  const memberCard2 = document.getElementById('member-bonus-card-bonus-page');
  const memberBtn2 = document.getElementById('member-bonus-claim-btn-bonus-page');
  const ds = currentUser?.depositWagered || 0, dr = currentUser?.depositWagerRequired || 0;
  const bs = currentUser?.bonusWagered || 0, br = currentUser?.bonusWagerRequired || 0;
  const setProgress = (textId, barId, done, required) => {
    const text = document.getElementById(textId), bar = document.getElementById(barId);
    if(text) text.innerText = `${fmt(done)} / ${fmt(required)} Ks`;
    if(bar) bar.style.width = `${required > 0 ? Math.min(100, Math.round(done / required * 100)) : 100}%`;
  };
  setProgress('deposit-turnover-text','deposit-turnover-bar',ds,dr);
  setProgress('bonus-turnover-text','bonus-turnover-bar',bs,br);
  const remaining = document.getElementById('turnover-remaining');
  if(remaining){
    const left = Math.max(0, dr-ds), bonusLeft = Math.max(0, br-bs);
    remaining.innerText = left || bonusLeft ? `ကျန်ရှိသော turnover: ${fmt(left + bonusLeft)} Ks` : 'ငွေထုတ်နိုင်ရန် turnover ပြည့်ပါပြီ';
    remaining.style.color = left || bonusLeft ? '#b45309' : '#0f766e';
  }
  if(memberCard && memberBtn){
    const available = Number(currentUser?.memberBonusAvailable || 0);
    memberCard.style.display = available > 0 ? 'block' : 'none';
    memberBtn.disabled = available <= 0;
  }
  if(memberCard2 && memberBtn2){
    const available = Number(currentUser?.memberBonusAvailable || 0);
    memberCard2.style.display = available > 0 ? 'block' : 'none';
    memberBtn2.disabled = available <= 0;
  }
}
async function claimMemberBonus(){
  if(!currentUser) return;
  const r = await fetch(`${API_BASE}/api/claim-member-bonus`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:currentUser.uid})});
  const d = await r.json();
  if(!d.success){showToast(d.message || 'Bonus unavailable');return;}
  const u = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
  const ud = await u.json();
  if(ud.success){currentUser=ud.user;updateUI();}
  showToast('10,000 Ks bonus claimed. Play 120,000 Ks before withdrawal.');
}

function updateBonusLock(){
  const w = currentUser ? (currentUser.wallet || {}) : {};
  const hasDeposited = (currentUser?.hasDeposited === true) || ((w.deposit||0) > 0);
  const notice = document.getElementById('bonus-locked-notice');
  const btn = document.getElementById('bonus-redeem-btn');
  if(!hasDeposited){
    notice.style.display = 'block';
    btn.disabled = true;
    btn.style.opacity = '0.5';
    btn.style.cursor = 'not-allowed';
  } else {
    notice.style.display = 'none';
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  }
}

function showWalletTab(tab,btn){
  document.querySelectorAll('.w-tab-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.w-content-box').forEach(b=>b.classList.remove('active'));
  document.getElementById(tab==='deposit'?'w-deposit-section':'w-withdraw-section').classList.add('active');
}

function selectPayMethod(m,el){
  selectedDepositMethod = m;
  document.querySelectorAll('#w-deposit-section .pay-method-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  updatePaymentInfo();
}

function selectWithdrawMethod(m,el){
  selectedWithdrawMethod = m;
  document.querySelectorAll('#w-withdraw-section .pay-method-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
}

function updatePaymentInfo(){
  if(!globalSettings) return;
  const phone = selectedDepositMethod === 'kpay' ? globalSettings.kpay_phone : globalSettings.wave_phone;
  const name = selectedDepositMethod === 'kpay' ? globalSettings.kpay_name : globalSettings.wave_name;
  document.getElementById('dep-phone').innerText = phone || '09691835083';
  document.getElementById('dep-name').innerText = name || 'သတ်မှတ်ရန်';
}

function fillDepAmt(a){document.getElementById('depAmount').value = a;}

async function processDeposit(ev){
  if(!currentUser) return;
  const id = document.getElementById('utrInput').value.trim();
  const a = parseInt(document.getElementById('depAmount').value);
  if(!a || a < 1000){showToast('Minimum 1,000 Ks');return;}
  if(!id || id.length < 6){showToast('Transaction ID ထည့်ပါ');return;}

  const btn = document.getElementById('depositBtn');
  const origText = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ပို့နေပါတယ်...';
  btn.disabled = true;
  showLoading();

  try{
    const r = await fetch(`${API_BASE}/api/deposit`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({uid:currentUser.uid,amount:a,utr:id,method:selectedDepositMethod})
    });
    const d = await r.json();
    if(d.success){
      playSound('notification');
      showToast(d.message);
      document.getElementById('depAmount').value='';
      document.getElementById('utrInput').value='';
      loadTransactionHistory();
    } else {
      showToast(d.message || 'Error');
    }
  }catch(e){showToast("Error: " + e.message);}
  finally{
    btn.innerHTML = origText;
    btn.disabled = false;
    hideLoading();
  }
}

async function handleWithdraw(){
  if(!currentUser) return;
  const a = parseInt(document.getElementById('withAmount').value);
  const phone = document.getElementById('withdrawPhone').value.trim();
  const name = document.getElementById('withdrawName').value.trim();
  const pw = document.getElementById('with-password').value;
  const minWithdraw = Number(globalSettings && globalSettings.min_withdraw) || 10000;
  if(a < minWithdraw){showToast(`Minimum ${fmt(minWithdraw)} Ks`);return;}
  if(!phone){showToast("ဖုန်းနံပါတ် ထည့်ပါ");return;}
  if(!name){showToast("အကောင့်အမည် ထည့်ပါ");return;}
  if(!pw){showToast("စကားဝှက် ထည့်ပါ");return;}
  showLoading();
  try{
    const r = await fetch(`${API_BASE}/api/withdraw`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({uid:currentUser.uid,amount:a,phone,name,password:pw,method:selectedWithdrawMethod})
    });
    const d = await r.json();
    if(d.success){
      showToast('Request submitted!');
      document.getElementById('withAmount').value='';
      document.getElementById('with-password').value='';
      const ur = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
      const ud = await ur.json();
      if(ud.success){currentUser = ud.user;updateUI();}
    } else showToast(d.message || 'Error');
  }catch(e){showToast("Error: " + e.message);}
  finally{hideLoading();}
}

async function loadTransactionHistory(){
  if(!currentUser) return;
  try{
    const r = await fetch(`${API_BASE}/api/history/${currentUser.uid}`);
    const d = await r.json();
    const list = document.getElementById('historyList');
    if(!d.success || d.history.length === 0){
      list.innerHTML = '<div style="text-align:center;color:#666;padding:20px;">No history</div>';
      return;
    }
    let html = '';
    d.history.forEach(h=>{
      const sign = h.type === 'Deposit' ? '+' : '-';
      let sC='tag-pending',aC='text-yellow',sT='Pending';
      if(h.status==='success'){sC='tag-success';aC='text-green';sT='Success';}
      else if(h.status==='rejected'){sC='tag-rejected';aC='text-red';sT='Rejected';}
      const dateStr = new Date(h.date).toLocaleString();
      const sub = h.type === 'Deposit' ? (h.method?h.method.toUpperCase()+' | '+(h.utr||'-'):(h.utr||'-')) : (h.method?h.method.toUpperCase()+' | '+(h.phone||''):(h.details||'-'));
      html += `<div class="hist-item ${h.type}">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;gap:10px;flex-wrap:wrap;">
          <h4 style="color:#fff;font-size:14px;">${h.type === 'Deposit' ? 'Deposit' : 'Withdraw'} <span style="font-size:10px;color:#666;">(${sub})</span></h4>
          <span class="${aC}" style="font-size:15px;font-weight:bold;">${sign}Ks ${fmt(h.amount)}</span>
        </div>
        <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <p style="font-size:11px;color:#aaa;">${dateStr}</p>
          <span class="${sC}">${sT}</span>
        </div>
      </div>`;
    });
    list.innerHTML = html;
  }catch(e){console.error(e);}
}

function nativeShare(){
  if(!currentUser) return;
  const code = currentUser.uid;
  const link = `${window.location.origin}?ref=${code}`;
  const msg = `Join GAG2026! Use my code *${code}* for bonus.\n${link}`;
  window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`,'_blank');
}

function copyToClipboard(t){
  navigator.clipboard.writeText(t);
  showToast("Copied: " + t);
}

function openSupport(){
  const link = globalSettings.support_link || 'https://t.me/YourSupport';
  window.open(link,'_blank');
}

async function redeemGiftCode(){
  if(!currentUser){showToast("Login first");return;}
  const w = currentUser.wallet || {};
  const hasDeposited = (currentUser.hasDeposited === true) || ((w.deposit||0) > 0);
  if(!hasDeposited){
    showToast("Deposit first to unlock bonus");
    return;
  }
  const code = document.getElementById('giftCodeInput').value.trim();
  if(!code){showToast("Enter code");return;}
  showLoading();
  try{
    const r = await fetch(`${API_BASE}/api/redeem-bonus`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({uid:currentUser.uid,code})
    });
    const d = await r.json();
    if(d.success){
      playSound('win');
      showToast(`Success! Ks ${fmt(d.amount)} bonus`);
      document.getElementById('giftCodeInput').value='';
      const ur = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
      const ud = await ur.json();
      if(ud.success){currentUser = ud.user;updateUI();}
      loadBonusHistory();
    } else showToast(d.message || 'Invalid');
  }catch(e){showToast("Error: " + e.message);}
  finally{hideLoading();}
}

async function loadBonusHistory(){
  if(!currentUser) return;
  try{
    const r = await fetch(`${API_BASE}/api/bonus-history/${currentUser.uid}`);
    const d = await r.json();
    const list = document.getElementById('bonus-history-list');
    if(d.success && d.history.length > 0){
      let html = '';
      d.history.forEach(h=>{
        const dateStr = new Date(h.timestamp).toLocaleString();
        html += `<div style="background:rgba(20,10,35,0.6);padding:12px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;border:1px solid rgba(157,78,221,0.3);gap:10px;">
          <div style="min-width:0;flex:1;">
            <div style="color:#FFD700;font-weight:bold;font-size:13px;word-break:break-all;">Gift: ${h.code}</div>
            <div style="color:#7a6b95;font-size:11px;">${dateStr}</div>
          </div>
          <div style="color:#28c76f;font-weight:bold;font-size:15px;white-space:nowrap;">+Ks ${fmt(h.amount)}</div>
        </div>`;
      });
      list.innerHTML = html;
    } else list.innerHTML = '<div style="text-align:center;color:#7a6b95;font-size:12px;">No history</div>';
  }catch(e){console.error(e);}
}

async function loadNotifications(){
  if(!currentUser) return;
  try{
    const r = await fetch(`${API_BASE}/api/notifications/${currentUser.uid}`);
    const d = await r.json();
    const list = document.getElementById('notifications-list');
    let html='',unread=0;
    const lastRead = parseInt(localStorage.getItem('last_read_notification_time')||'0');
    if(d.success && d.notifications.length > 0){
      d.notifications.forEach(n=>{
        const t = n.timestamp ? new Date(n.timestamp).toLocaleString() : '';
        if(n.timestamp && new Date(n.timestamp).getTime() > lastRead) unread++;
        html += `<div class="notif-item">
          <div class="notif-title">${n.title}</div>
          <div class="notif-body">${n.message}</div>
          <span class="notif-time">${t}</span>
        </div>`;
      });
    } else html = '<div style="text-align:center;color:#666;padding:20px;">No notifications</div>';
    list.innerHTML = html;
    const badge = document.getElementById('notif-badge');
    if(unread > 0){badge.innerText=unread;badge.style.display='flex';}
    else badge.style.display='none';
  }catch(e){console.error(e);}
}

function initAllHistories(){
  [30,60,180,300].forEach(async dur=>{
    gameData[dur].period = getPeriodId(dur);
    const r = await fetch(`${API_BASE}/api/game-history/${dur}`);
    const d = await r.json();
    if(d.success && d.history) gameData[dur].history = d.history;
  });
}

function getPeriodId(dur){
  const now = new Date();
  const totalSec = Math.floor(now.getTime()/1000);
  const dtStr = now.toISOString().slice(0,10).replace(/-/g,'');
  const midnight = new Date(now.getFullYear(),now.getMonth(),now.getDate()).getTime()/1000;
  const idx = Math.floor((totalSec - midnight) / dur);
  const gid = dur===30?'1':dur===60?'2':dur===180?'3':'5';
  return dtStr + gid + String(idx).padStart(4,'0');
}

function generateResult(pid,dur){
  const combined = pid + "_" + dur;
  let seed = 0;
  for(let i=0;i<combined.length;i++){
    seed = (seed ^ combined.charCodeAt(i)) * 0x5bd1e995;
    seed = seed ^ (seed >>> 15);
  }
  let t = (seed + 0x6D2B79F5) >>> 0;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t = (t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))) >>> 0;
  const rand = ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  const n = Math.floor(rand * 10);
  let c = 'green';
  if([2,4,6,8].includes(n)) c='red';
  if(n===0) c='red-v';
  if(n===5) c='green-v';
  return {period:pid,number:n,size:n>=5?'Big':'Small',color:c};
}

async function updateTimers(){
  const now = new Date();
  const seconds = now.getSeconds() + now.getMinutes()*60 + now.getHours()*3600;
  [30,60,180,300].forEach(dur=>{
    const rem = dur - (seconds % dur);
    const liveP = getPeriodId(dur);
    if(gameData[dur].period !== liveP){
      const finished = gameData[dur].period;
      if(!gameData[dur].history.some(h=>h.period===finished)){
        const res = generateResult(finished,dur);
        gameData[dur].history.unshift(res);
        if(gameData[dur].history.length > 500) gameData[dur].history.pop();
        fetch(`${API_BASE}/api/save-result`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...res,duration:dur})}).catch(e=>{});
        checkBets(dur,finished,res);
      }
      gameData[dur].period = liveP;
      if(currTime === dur) renderActiveTab();
    }
    if(currTime === dur){
      document.getElementById('period-display').innerText = liveP;
      const mm = Math.floor(rem/60), ss = rem%60;
      document.getElementById('min').innerText = mm<10?'0'+mm:mm;
      document.getElementById('sec').innerText = ss<10?'0'+ss:ss;
      if(rem <= 5){
        document.getElementById('countdown-overlay').style.display = 'flex';
        document.getElementById('cd-1').innerText = 0;
        document.getElementById('cd-2').innerText = rem;
        document.getElementById('game-area').classList.add('locked');
        closeBet();
        if(rem !== window.lastTick){ window.lastTick = rem; playSound('tick'); }
      } else {
        document.getElementById('countdown-overlay').style.display = 'none';
        document.getElementById('game-area').classList.remove('locked');
      }
    }
  });
}

async function checkBets(dur,period,res){
  if(!currentUser) return;
  try{
    const r = await fetch(`${API_BASE}/api/check-bets`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({uid:currentUser.uid,duration:dur,period,result:res})
    });
    const d = await r.json();
    if(d.success){
      if(d.total_win > 0){
        const ur = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
        const ud = await ur.json();
        if(ud.success){currentUser = ud.user;updateUI();}
        if(currTime === dur) showWinPopup(d.total_win,res);
      } else if(d.had_bets && currTime === dur) showLossPopup(res);
      loadUserBetHistory();
    }
  }catch(e){console.error(e);}
}

async function loadUserBetHistory(){
  if(!currentUser) return;
  try{
    const r = await fetch(`${API_BASE}/api/user-bets/${currentUser.uid}`);
    const d = await r.json();
    if(d.success){
      activeWingoBets = d.bets;
      if(document.getElementById('wingo-game-container').classList.contains('active')) renderMyBets();
    }
  }catch(e){console.error(e);}
}

async function openWingoGame(){
  if(!currentUser){showToast("Login first");return;}
  showLoading();
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('main-header').style.display = 'none';
  document.getElementById('wingo-game-container').classList.add('active');
  document.getElementById('main-navbar').classList.add('hidden');
  document.getElementById('support-fab').style.display = 'none';
  updateUI();
  if(!gameInterval){
    initAllHistories();
    gameInterval = setInterval(updateTimers,1000);
    renderActiveTab();
  }
  setTimeout(hideLoading, 800);
}

function closeWingoGame(){
  document.getElementById('wingo-game-container').classList.remove('active');
  document.getElementById('main-header').style.display = 'flex';
  document.getElementById('main-navbar').classList.remove('hidden');
  document.getElementById('home').classList.add('active');
  document.getElementById('support-fab').style.display = 'flex';
  if(gameInterval){clearInterval(gameInterval);gameInterval=null;}
}

function switchTime(t,el){
  currTime = t; currentPage = 1; currentMyBetPage = 1;
  document.querySelectorAll('.time-tab').forEach(x=>x.classList.remove('active'));
  el.classList.add('active');
  const label = t===30?"30s":t===60?"1m":t===180?"3m":"5m";
  document.getElementById('bs-time').innerText = label;
  document.getElementById('curr-time-disp').innerText = label;
  renderActiveTab();
}

function showTab(tab,el){
  document.querySelectorAll('.r-tab').forEach(x=>x.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('chart-content').style.display = tab==='chart'?'block':'none';
  document.getElementById('history-content').style.display = tab==='history'?'block':'none';
  document.getElementById('mybet-content').style.display = tab==='mybet'?'block':'none';
  if(tab==='chart') setTimeout(drawLines,50);
  if(tab==='mybet') renderMyBets();
}

function changePage(d){
  if(d===1 && currentPage < 50) currentPage++;
  else if(d===-1 && currentPage > 1) currentPage--;
  renderActiveTab();
}

function changeMyBetPage(d){
  let maxP = Math.ceil(activeWingoBets.filter(b=>b.gameTimer===currTime).length/10);
  if(maxP < 1) maxP = 1;
  if(d===1 && currentMyBetPage < maxP) currentMyBetPage++;
  else if(d===-1 && currentMyBetPage > 1) currentMyBetPage--;
  renderMyBets();
}

function renderActiveTab(){
  const hist = gameData[currTime].history;
  const start = (currentPage-1)*10;
  const disp = hist.slice(start,start+10);
  document.getElementById('page-info').innerText = `${currentPage}/50`;
  let chartHtml = '';
  hist.slice(0,10).forEach(r=>{
    let wc = 'winning';
    if(r.color === 'red-v') wc += ' mix0';
    else if(r.color === 'green-v') wc += ' mix5';
    else if(r.color === 'green') wc += ' green';
    else if(r.color === 'red') wc += ' red';
    chartHtml += `<div class="c-row"><div class="c-period">${r.period.slice(-4)}</div>
      <div class="c-nums">${[0,1,2,3,4,5,6,7,8,9].map(n=>`<div class="${n===r.number?'c-num '+wc:'c-num'}">${n}</div>`).join('')}</div>
      <div class="c-result-icon ${r.size==='Big'?'icon-B':'icon-S'}">${r.size==='Big'?'B':'S'}</div></div>`;
  });
  document.getElementById('chart-rows').innerHTML = chartHtml;
  let tblHtml = '';
  disp.forEach(r=>{
    let ns = '';
    if(r.number === 0) ns = 'background:linear-gradient(135deg,#ea5455 55%,#9c27b0 50%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:900;';
    else if(r.number === 5) ns = 'background:linear-gradient(135deg,#28c76f 55%,#9c27b0 50%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:900;';
    else ns = `color:${r.color==='green'?'#28c76f':'#ea5455'}`;
    let dh = '';
    if(r.color === 'red-v') dh = '<div class="dot-mix-red-violet"></div>';
    else if(r.color === 'green-v') dh = '<div class="dot-mix-green-violet"></div>';
    else if(r.color === 'green') dh = '<div class="dot-single" style="background:#28c76f;"></div>';
    else dh = '<div class="dot-single" style="background:#ea5455;"></div>';
    tblHtml += `<tr><td>${r.period}</td><td style="${ns}font-weight:900;font-size:16px;">${r.number}</td>
      <td style="color:${r.size==='Big'?'#ffc107':'#3d8bff'};font-weight:bold;">${r.size==='Big'?'Big':'Small'}</td><td>${dh}</td></tr>`;
  });
  document.getElementById('gh-body').innerHTML = tblHtml;
  renderMyBets();
  if(document.getElementById('chart-content').style.display === 'block') setTimeout(drawLines,50);
}

function renderMyBets(){
  const all = activeWingoBets.filter(b=>b.gameTimer===currTime).sort((a,b)=>b.period-a.period);
  const list = document.getElementById('my-bets-list');
  if(all.length === 0){
    list.innerHTML = '<div style="text-align:center;color:#FFD700;padding:20px;">No bets</div>';
    document.getElementById('my-bet-pagination').style.display = 'none';
    return;
  }
  const maxP = Math.ceil(all.length/10);
  if(currentMyBetPage > maxP) currentMyBetPage = maxP;
  if(currentMyBetPage < 1) currentMyBetPage = 1;
  document.getElementById('my-bet-page-info').innerText = `${currentMyBetPage}/${maxP}`;
  document.getElementById('my-bet-pagination').style.display = 'flex';
  const start = (currentMyBetPage-1)*10;
  const disp = all.slice(start,start+10);
  let html = '';
  disp.forEach(b=>{
    let bc = 'box-Num';
    if(b.select === 'Big') bc = 'box-Big';
    else if(b.select === 'Small') bc = 'box-Small';
    else if(b.select === 'Green') bc = 'box-Green';
    else if(b.select === 'Red') bc = 'box-Red';
    else if(b.select === 'Violet') bc = 'box-Violet';
    const selDisplay = b.select;
    let st = 'Pending',sc = 'st-pending',ac = 'text-wait',da = `-Ks ${fmt(b.amount)}`;
    if(b.status === 'win'){st='Win';sc='st-success';ac='text-plus';da=`+Ks ${fmt(b.payout||0)}`;}
    else if(b.status === 'loss'){st='Loss';sc='st-failed';ac='text-minus';da=`-Ks ${fmt(b.amount)}`;}
    const t = b.timestamp ? new Date(b.timestamp).toISOString().slice(0,19).replace('T',' ') : '';
    html += `<div class="mb-item">
      <div class="mb-icon ${bc}">${selDisplay}</div>
      <div class="mb-details"><div class="mb-period">${b.period}</div><div class="mb-time">${t}</div></div>
      <div class="mb-right"><span class="mb-status-btn ${sc}">${st}</span><br><span class="mb-amt ${ac}">${da}</span></div>
    </div>`;
  });
  list.innerHTML = html;
}

function drawLines(){
  const svg = document.getElementById('chart-svg');
  const rows = document.querySelectorAll('.c-row');
  const cont = document.getElementById('chart-scroll-area');
  if(!cont || !svg) return;
  svg.setAttribute('width',cont.scrollWidth);
  svg.setAttribute('height',cont.scrollHeight);
  svg.innerHTML = '';
  let px = null, py = null;
  rows.forEach(r=>{
    const w = r.querySelector('.c-num.winning') || r.querySelector('.c-num.mix0') || r.querySelector('.c-num.mix5') || r.querySelector('.c-num.green') || r.querySelector('.c-num.red');
    if(w){
      const rect = w.getBoundingClientRect(), cr = cont.getBoundingClientRect();
      const x = rect.left + rect.width/2 - cr.left + cont.scrollLeft;
      const y = rect.top + rect.height/2 - cr.top + cont.scrollTop;
      if(px !== null){
        const ln = document.createElementNS('http://www.w3.org/2000/svg','line');
        ln.setAttribute('x1',px); ln.setAttribute('y1',py);
        ln.setAttribute('x2',x); ln.setAttribute('y2',y);
        ln.setAttribute('stroke','#FFD700'); ln.setAttribute('stroke-width','1.5');
        svg.appendChild(ln);
      }
      px = x; py = y;
    }
  });
}

function openBet(v){
  selectedBet = v;
  document.getElementById('bs-select-display').innerText = v==='Big'?'BIG':v==='Small'?'SMALL':v==='Green'?'GREEN':v==='Red'?'RED':v==='Violet'?'VIOLET':'NUMBER '+v;
  document.getElementById('bet-overlay').classList.add('active');
  document.getElementById('bet-sheet').classList.add('active');
  amt = 100; qty = 1; mul = 1; updateCalc();
  playSound('bet');
}

function closeBet(){
  document.getElementById('bet-overlay').classList.remove('active');
  document.getElementById('bet-sheet').classList.remove('active');
}

function setAmt(v){amt = v;updateCalc();}
function setMul(v){mul = v;updateCalc();}
function addQty(v){qty = Math.max(1,qty+v);updateCalc();}

function updateCalc(){
  document.getElementById('qty-display').innerText = qty;
  document.getElementById('total-amt').innerText = fmt(amt*qty*mul);
  document.querySelectorAll('.money-btn').forEach(b=>{
    b.classList.remove('active');
    if(parseInt(b.innerText.replace('X','')) === mul && b.innerText.includes('X')) b.classList.add('active');
    if(parseInt(b.innerText) === amt && !b.innerText.includes('X')) b.classList.add('active');
  });
}

async function placeBet(){
  if(!currentUser){showToast("Login first");return;}
  const tot = amt * qty * mul;
  if(getPlayableBalance() < tot){showToast("Insufficient balance");return;}
  const p = gameData[currTime].period;
  if(gameData[currTime].history.some(h=>h.period === p)){showToast("Round ended");return;}
  try{
    const r = await fetch(`${API_BASE}/api/place-bet`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({uid:currentUser.uid,period:p,gameTimer:currTime,select:selectedBet,amount:tot})
    });
    const d = await r.json();
    if(d.success){
      playSound('bet');
      showToast("Bet placed!");
      closeBet();
      const ur = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
      const ud = await ur.json();
      if(ud.success){currentUser = ud.user;updateUI();}
      loadUserBetHistory();
    } else showToast(d.message || "Error");
  }catch(e){showToast("Error: " + e.message);}
}

function showWinPopup(a,res){
  playSound('win');
  let h = '';
  if(res.color.includes('red')) h += `<div class="win-pill" style="background:#ea5455">RED</div>`;
  if(res.color.includes('green')) h += `<div class="win-pill" style="background:#28c76f">GREEN</div>`;
  if(res.color.includes('v')) h += `<div class="win-pill" style="background:#9c27b0">VIOLET</div>`;
  h += `<div class="win-pill" style="background:#fff;color:#000;">${res.number}</div>`;
  document.getElementById('win-res-row').innerHTML = h;
  document.getElementById('win-amount').innerText = "Ks " + fmt(a);
  document.getElementById('win-popup').style.display = 'flex';
  setTimeout(()=>{document.getElementById('win-popup').style.display='none';},3000);
}

function showLossPopup(res){
  playSound('lose');
  document.getElementById('loss-res-txt').innerText = `Result: ${res.number} (${res.size})`;
  document.getElementById('loss-popup').style.display = 'flex';
}

function closePopup(){
  document.getElementById('win-popup').style.display = 'none';
  document.getElementById('loss-popup').style.display = 'none';
}

function showToast(msg){
  const x = document.getElementById("toast");
  x.innerText = msg;
  x.className = "show";
  setTimeout(()=>{x.className = x.className.replace("show","");},3000);
}

function startLeaderboard(){
  const l = document.getElementById('lb-list');
  if(!l) return;
  const av = ['A','B','C','D','K','M','R','S','T'];
  function add(){
    const code = 'User***' + Math.floor(Math.random()*899+100);
    const a = (Math.floor(Math.random()*50)+1)*1000;
    const i = av[Math.floor(Math.random()*av.length)];
    const item = document.createElement('div');
    item.className = 'lb-item';
    item.innerHTML = `<div class="lb-user"><div class="lb-avatar">${i}</div><span>${code}</span></div><div class="lb-amount">+ Ks ${fmt(a)}</div>`;
    l.insertBefore(item,l.firstChild);
    if(l.children.length > 5) l.removeChild(l.lastChild);
  }
  for(let i=0;i<3;i++) add();
  setInterval(add,3000);
}

function applyTheme(){ document.body.setAttribute('data-theme','light'); }
applyTheme();

// ============ INIT ============
showLoading();
window.addEventListener('load', async ()=>{
  await loadSettings();
  await loadDemoGames();
  checkLoginStatus();
  startLeaderboard();
  setInterval(()=>{if(currentUser) loadNotifications();},30000);
  setInterval(async ()=>{
    if(currentUser){
      const r = await fetch(`${API_BASE}/api/user/${currentUser.uid}`);
      const d = await r.json();
      if(d.success){currentUser = d.user;updateUI();}
    }
  },10000);
  setTimeout(hideLoading, 1500);
});
window.addEventListener('resize',drawLines);
</script>
</body>
</html>
'''
# ============================================================
# ADMIN LOGIN HTML
# ============================================================
ADMIN_LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GAG2026 Admin</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800;900&family=Padauk:wght@400;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins','Padauk',sans-serif;}
body{
  background:radial-gradient(circle at top, #2a0e4e 0%, #050208 100%);
  min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;
}
.login-box{
  background:rgba(20,10,35,0.85);
  padding:40px 30px;border-radius:22px;
  border:1px solid rgba(255,215,0,0.3);
  text-align:center;width:100%;max-width:380px;
  backdrop-filter:blur(20px);
  box-shadow:0 20px 60px rgba(90,24,154,0.5), 0 0 40px rgba(255,215,0,0.1);
  position:relative;overflow:hidden;
}
.login-box::before{
  content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;
  background:radial-gradient(circle, rgba(157,78,221,0.2), transparent 70%);
  animation:rotate 10s linear infinite;pointer-events:none;
}
@keyframes rotate{to{transform:rotate(360deg);}}
h2{
  font-family:'Orbitron',sans-serif;
  color:#FFD700;margin-bottom:8px;letter-spacing:2px;
  display:flex;align-items:center;justify-content:center;gap:12px;
  position:relative;z-index:1;
  font-size:24px;
  text-shadow:0 0 20px rgba(255,215,0,0.6);
}
p.sub{color:#9D4EDD;font-size:12px;margin-bottom:28px;position:relative;z-index:1;letter-spacing:1px;}
.input-wrap{position:relative;z-index:1;margin-bottom:14px;}
.input-wrap i{
  position:absolute;left:16px;top:50%;transform:translateY(-50%);
  color:#9D4EDD;font-size:14px;
}
input{
  width:100%;padding:14px 14px 14px 44px;
  background:rgba(15,5,30,0.9);
  border:1px solid rgba(157,78,221,0.3);
  color:#fff;border-radius:12px;outline:none;font-size:14px;
  transition:0.3s;
}
input:focus{border-color:#FFD700;box-shadow:0 0 0 3px rgba(255,215,0,0.15);}
input::placeholder{color:#5a4a75;}
button{
  width:100%;padding:14px;margin-top:20px;
  background:linear-gradient(135deg,#FFD700 0%,#FFA500 50%,#B8860B 100%);
  border:none;color:#1a0a2e;font-weight:900;border-radius:12px;
  cursor:pointer;font-size:15px;
  position:relative;z-index:1;
  box-shadow:0 8px 25px rgba(255,165,0,0.4), inset 0 1px 0 rgba(255,255,255,0.4);
  font-family:'Orbitron',sans-serif;
  letter-spacing:1px;
  display:flex;align-items:center;justify-content:center;gap:8px;
}
button:active{transform:scale(0.98);}
.error{color:#ef4444;font-size:13px;margin-top:15px;position:relative;z-index:1;}
.hint{color:#5a4a75;font-size:11px;margin-top:20px;position:relative;z-index:1;}
.hint code{color:#FFD700;background:rgba(255,215,0,0.1);padding:2px 6px;border-radius:4px;}
</style>
</head>
<body>
<div class="login-box">
  <h2><i class="fa-solid fa-crown"></i> GAG2026</h2>
  <p class="sub">SECURE ADMIN PANEL</p>
  <form method="POST">
    <div class="input-wrap">
      <i class="fa-solid fa-user"></i>
      <input type="text" name="username" placeholder="Username" required>
    </div>
    <div class="input-wrap">
      <i class="fa-solid fa-lock"></i>
      <input type="password" name="password" placeholder="Password" required>
    </div>
    <button type="submit"><i class="fa-solid fa-right-to-bracket"></i> ACCESS</button>
  </form>
  {% if error %}<div class="error"><i class="fa-solid fa-circle-exclamation"></i> {{ error }}</div>{% endif %}
  <div class="hint">Default: <code>admin</code> / <code>jalwa123</code></div>
</div>
</body>
</html>
'''

# ============================================================
# ADMIN PANEL HTML
# ============================================================
ADMIN_HTML = r'''
<!DOCTYPE html>
<html lang="my">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GAG2026 Admin Panel</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Padauk:wght@400;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root{
  --bg-dark:#050208;
  --sidebar-bg:#0f0520;
  --card-bg:rgba(20,10,35,0.85);
  --primary:#FFD700;
  --primary-2:#FFA500;
  --purple:#9D4EDD;
  --purple-dark:#5A189A;
  --cyan:#00E5FF;
  --text-white:#fff;
  --text-gray:#a8a4b8;
  --danger:#ef4444;
  --success:#22c55e;
}
*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins','Padauk',sans-serif;}
body{background:var(--bg-dark);color:var(--text-white);display:flex;min-height:100vh;overflow-x:hidden;}
body::before{
  content:'';position:fixed;top:0;left:0;width:100%;height:100%;
  background:radial-gradient(ellipse at top, rgba(157,78,221,0.15), transparent 60%);
  pointer-events:none;z-index:0;
}
.sidebar-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:900;display:none;}
.sidebar-overlay.active{display:block;}
.sidebar{
  width:270px;
  background:linear-gradient(180deg, #15071f, #0a0312);
  height:100vh;display:flex;flex-direction:column;
  position:fixed;top:0;left:-270px;border-right:1px solid rgba(255,215,0,0.15);
  overflow-y:auto;z-index:1000;transition:left 0.3s cubic-bezier(0.4,0,0.2,1);
  box-shadow:5px 0 30px rgba(90,24,154,0.3);
}
.sidebar.active{left:0;}
.brand{
  padding:22px 20px;font-family:'Orbitron',sans-serif;
  font-size:18px;font-weight:900;
  background:linear-gradient(180deg,#FFD700,#FFA500,#B8860B);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  border-bottom:1px solid rgba(255,215,0,0.15);
  display:flex;align-items:center;gap:10px;
  background-color:rgba(20,10,35,0.5);
  filter:drop-shadow(0 2px 6px rgba(255,215,0,0.3));
}
.menu{padding:10px 0;flex:1;}
.menu-item{
  padding:14px 22px;color:var(--text-gray);cursor:pointer;
  display:flex;align-items:center;gap:12px;font-size:13px;
  border-left:3px solid transparent;transition:0.2s;
}
.menu-item:hover,.menu-item.active{
  background:linear-gradient(90deg, rgba(157,78,221,0.25), transparent);
  color:#fff;border-left-color:var(--primary);
}
.menu-item i{width:20px;text-align:center;font-size:15px;color:var(--primary);}
.main-content{flex:1;margin-left:0;display:flex;flex-direction:column;min-height:100vh;width:100%;position:relative;z-index:1;}
header{
  background:linear-gradient(90deg, rgba(90,24,154,0.5), rgba(40,10,70,0.7));
  backdrop-filter:blur(15px);
  padding:15px 20px;display:flex;justify-content:space-between;align-items:center;
  border-bottom:1px solid rgba(255,215,0,0.2);position:sticky;top:0;z-index:50;
  box-shadow:0 4px 20px rgba(90,24,154,0.4);
}
.page-container{padding:20px;flex:1;}
.section{display:none;}
.section.active{display:block;animation:fadeIn 0.4s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;}
.stat-card{
  background:var(--card-bg);
  padding:20px;border-radius:16px;
  display:flex;align-items:center;gap:15px;
  border:1px solid rgba(157,78,221,0.3);min-width:0;
  backdrop-filter:blur(10px);
  transition:0.3s;
}
.stat-card:hover{transform:translateY(-3px);border-color:rgba(255,215,0,0.4);box-shadow:0 8px 25px rgba(90,24,154,0.4);}
.stat-card .st-val{font-size:22px;font-weight:700;display:block;color:#fff;}
.stat-card span{color:#a8a4b8;font-size:11px;}
.icon-box{
  width:52px;height:52px;border-radius:14px;
  display:flex;justify-content:center;align-items:center;
  font-size:22px;flex-shrink:0;
}
.ib-blue{background:rgba(59,130,246,0.15);color:#3b82f6;}
.ib-green{background:rgba(34,197,94,0.15);color:#22c55e;}
.ib-red{background:rgba(239,68,68,0.15);color:#ef4444;}
.ib-gold{background:rgba(255,215,0,0.15);color:#FFD700;}
.ib-purple{background:rgba(157,78,221,0.15);color:#9D4EDD;}
.ib-cyan{background:rgba(0,229,255,0.15);color:#00E5FF;}
.table-card{
  background:var(--card-bg);
  border-radius:16px;overflow:hidden;
  border:1px solid rgba(157,78,221,0.3);
  margin-top:20px;
  backdrop-filter:blur(10px);
}
.table-header{
  padding:18px 22px;
  background:linear-gradient(90deg, rgba(157,78,221,0.2), rgba(40,10,70,0.3));
  font-weight:600;font-size:14px;
  color:var(--primary);
  display:flex;justify-content:space-between;align-items:center;
  border-bottom:1px solid rgba(157,78,221,0.2);flex-wrap:wrap;gap:10px;
}
table{width:100%;border-collapse:collapse;font-size:12px;color:#ccc;}
th,td{padding:12px 10px;text-align:left;border-bottom:1px solid rgba(157,78,221,0.15);}
th{color:#fff;background:rgba(10,5,20,0.7);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:0.5px;}
.badge{padding:4px 10px;border-radius:50px;font-size:10px;font-weight:bold;text-transform:uppercase;display:inline-block;white-space:nowrap;}
.bg-pending{background:rgba(255,193,7,0.15);color:#ffc107;}
.bg-success{background:rgba(34,197,94,0.15);color:#22c55e;}
.bg-reject{background:rgba(239,68,68,0.15);color:#ef4444;}
.bg-banned{background:#ef4444;color:#fff;padding:3px 8px;border-radius:4px;font-size:10px;}
.btn-action-green{padding:6px 12px;border:none;border-radius:8px;font-size:10px;font-weight:bold;cursor:pointer;background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;white-space:nowrap;box-shadow:0 2px 8px rgba(34,197,94,0.3);}
.btn-action-red{padding:6px 12px;border:none;border-radius:8px;font-size:10px;font-weight:bold;cursor:pointer;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;margin-left:5px;white-space:nowrap;box-shadow:0 2px 8px rgba(239,68,68,0.3);}
.btn-action-blue{padding:6px 12px;border:none;border-radius:8px;font-size:10px;font-weight:bold;cursor:pointer;background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;white-space:nowrap;box-shadow:0 2px 8px rgba(59,130,246,0.3);}
.btn-action-purple{padding:6px 12px;border:none;border-radius:8px;font-size:10px;font-weight:bold;cursor:pointer;background:linear-gradient(135deg,#9D4EDD,#7c3aed);color:#fff;white-space:nowrap;box-shadow:0 2px 8px rgba(157,78,221,0.3);}
.btn-action-gold{padding:6px 12px;border:none;border-radius:8px;font-size:10px;font-weight:bold;cursor:pointer;background:linear-gradient(135deg,#FFD700,#FFA500);color:#1a0a2e;white-space:nowrap;box-shadow:0 2px 8px rgba(255,165,0,0.3);}
.form-control{
  width:100%;padding:12px;
  background:rgba(15,5,30,0.9);
  border:1px solid rgba(157,78,221,0.3);
  color:#fff;border-radius:10px;outline:none;font-size:13px;margin-bottom:15px;
  transition:0.3s;
}
.form-control:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(255,215,0,0.1);}
.form-control::placeholder{color:#5a4a75;}
label{font-size:12px;color:#a8a4b8;display:block;margin-bottom:6px;font-weight:500;}
.btn-primary{
  background:linear-gradient(135deg,#FFD700,#FFA500);
  color:#1a0a2e;padding:13px 25px;border:none;border-radius:12px;
  font-weight:800;cursor:pointer;width:100%;font-size:14px;
  display:flex;align-items:center;justify-content:center;gap:8px;
  box-shadow:0 8px 25px rgba(255,165,0,0.4), inset 0 1px 0 rgba(255,255,255,0.4);
  font-family:'Orbitron',sans-serif;
  letter-spacing:0.5px;
  transition:0.3s;
}
.btn-primary:hover{transform:translateY(-2px);}
.btn-primary:active{transform:translateY(0);}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:15px;}
.three-col{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:2000;display:none;justify-content:center;align-items:center;padding:20px;}
.modal-overlay.active{display:flex;}
.modal-box{
  background:linear-gradient(180deg, #1a0a2e, #0a0312);
  width:100%;max-width:450px;border-radius:20px;
  border:1px solid rgba(255,215,0,0.3);overflow:hidden;
  max-height:90vh;overflow-y:auto;
  box-shadow:0 20px 60px rgba(90,24,154,0.5);
}
.modal-header{
  background:linear-gradient(90deg,#FFD700,#FFA500);
  padding:15px 20px;color:#1a0a2e;font-weight:800;
  display:flex;justify-content:space-between;align-items:center;font-size:15px;
  font-family:'Orbitron',sans-serif;
}
.modal-body{padding:25px;}
.info-row{
  display:flex;justify-content:space-between;margin-bottom:12px;
  font-size:13px;border-bottom:1px solid rgba(157,78,221,0.15);
  padding-bottom:10px;gap:10px;flex-wrap:wrap;
}
.info-row span:first-child{color:#a8a4b8;}
.info-row span:last-child{color:#fff;font-weight:600;}
.modal-footer{padding:15px;display:flex;gap:10px;border-top:1px solid rgba(157,78,221,0.15);background:rgba(10,5,20,0.7);}
.m-btn{
  flex:1;padding:12px;border:none;border-radius:10px;
  font-weight:bold;cursor:pointer;text-transform:uppercase;font-size:12px;
  display:flex;align-items:center;justify-content:center;gap:6px;
}
.m-btn-reject{background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);}
.m-btn-approve{background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;}
.m-btn-ban{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;}
.toggle-btn{display:block;font-size:22px;cursor:pointer;color:var(--primary);}
.logo-upload-box{
  background:rgba(15,5,30,0.9);
  border:2px dashed rgba(157,78,221,0.4);
  border-radius:12px;padding:20px;text-align:center;
  cursor:pointer;margin-bottom:15px;transition:0.3s;
}
.logo-upload-box:hover{border-color:var(--primary);background:rgba(157,78,221,0.1);}
.logo-upload-box i{font-size:30px;color:#5a4a75;margin-bottom:10px;}
.logo-upload-box p{font-size:12px;color:#a8a4b8;}
.logo-upload-box input{display:none;}
.logo-preview{
  width:100%;height:100px;object-fit:contain;
  border-radius:12px;margin-bottom:10px;
  border:1px solid rgba(157,78,221,0.3);
  background:#000;padding:5px;
}
.slider-preview{
  width:100%;height:100px;object-fit:cover;
  border-radius:12px;margin-bottom:10px;
  border:1px solid rgba(157,78,221,0.3);
}
.section-title-admin{
  font-family:'Orbitron',sans-serif;
  color:var(--primary);
  margin-bottom:20px;font-size:16px;
  display:flex;align-items:center;gap:10px;
  text-shadow:0 0 20px rgba(255,215,0,0.4);
  letter-spacing:1px;
}
.section-title-admin i{font-size:18px;}
@media (max-width:768px){
  .sidebar{left:-270px;}
  .sidebar.active{left:0;}
  .main-content{margin-left:0;}
  .stats-grid{grid-template-columns:1fr 1fr;gap:10px;}
  .stat-card{padding:15px;}
  .stat-card .st-val{font-size:18px;}
  .icon-box{width:40px;height:40px;font-size:18px;}
  .two-col{grid-template-columns:1fr;}
  .page-container{padding:15px;}
  table{font-size:11px;}
  th,td{padding:10px 8px;}
}
body[data-theme="light"]{--bg-dark:#f4f6f8;--sidebar-bg:#fff;--card-bg:#fff;--text-white:#172033;--text-gray:#64748b;background:#f4f6f8;color:#172033;}
body[data-theme="light"]::before{display:none;}
body[data-theme="light"] .sidebar{background:#fff;border-right-color:#e2e8f0;box-shadow:4px 0 18px rgba(15,23,42,.06);}
body[data-theme="light"] .brand{background:linear-gradient(180deg,#334155,#0f172a);-webkit-background-clip:text;background-clip:text;border-bottom-color:#e2e8f0;filter:none;}
body[data-theme="light"] .main-content header{background:rgba(255,255,255,.96);border-bottom-color:#e2e8f0;box-shadow:0 3px 16px rgba(15,23,42,.06);}
body[data-theme="light"] .stat-card,body[data-theme="light"] .table-card,body[data-theme="light"] .settings-card,body[data-theme="light"] .modal-content{background:#fff;border-color:#e2e8f0;box-shadow:0 8px 24px rgba(15,23,42,.06);}
body[data-theme="light"] .table-card th{background:#f8fafc;color:#475569;}
.admin-theme-toggle{width:36px;height:34px;padding:0;margin:0;border:1px solid rgba(148,163,184,.35);border-radius:9px;background:rgba(255,255,255,.08);color:var(--primary);cursor:pointer;}
body[data-theme="light"] .admin-theme-toggle{background:#f1f5f9;color:#334155;border-color:#cbd5e1;}
</style>
</head>
<body>

<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

<div class="sidebar" id="sidebar">
  <div class="brand"><i class="fa-solid fa-crown"></i> GAG2026</div>
  <div class="menu">
    <div class="menu-item active" onclick="showSection('dashboard',this)"><i class="fa-solid fa-house"></i> Dashboard</div>
    <div class="menu-item" onclick="showSection('deposit',this)"><i class="fa-solid fa-wallet"></i> Deposits</div>
    <div class="menu-item" onclick="showSection('withdraw',this)"><i class="fa-solid fa-money-bill-transfer"></i> Withdrawals</div>
    <div class="menu-item" onclick="showSection('users',this)"><i class="fa-solid fa-users"></i> Users + Download</div>
    <div class="menu-item" onclick="showSection('mainapi',this)"><i class="fa-solid fa-code"></i> Main API</div>
    <div class="menu-item" onclick="showSection('game',this)"><i class="fa-solid fa-gamepad"></i> Game Control</div>
    <div class="menu-item" onclick="showSection('notifications',this)"><i class="fa-solid fa-bell"></i> Notifications</div>
    <div class="menu-item" onclick="showSection('payment',this)"><i class="fa-solid fa-credit-card"></i> KPay/Wave + Logos</div>
    <div class="menu-item" onclick="showSection('slider',this)"><i class="fa-solid fa-image"></i> Sliders</div>
    <div class="menu-item" onclick="showSection('bonus',this)"><i class="fa-solid fa-gift"></i> Gift Codes</div>
    <div class="menu-item" onclick="showSection('appconfig',this)"><i class="fa-solid fa-cog"></i> App + Backgrounds</div>
    <div class="menu-item" onclick="showSection('admincred',this)"><i class="fa-solid fa-user-shield"></i> Admin Credentials</div>
    <div class="menu-item" onclick="logoutAdmin()" style="color:var(--danger);margin-top:20px;"><i class="fa-solid fa-power-off"></i> Logout</div>
  </div>
</div>

<div class="main-content">
  <header>
    <div style="display:flex;align-items:center;gap:15px;">
      <i class="fa-solid fa-bars toggle-btn" onclick="toggleSidebar()"></i>
      <h3 id="page-title" style="letter-spacing:1px;font-weight:600;font-size:16px;font-family:'Orbitron',sans-serif;color:#FFD700;">DASHBOARD</h3>
    </div>
    <div style="display:flex;align-items:center;gap:10px;"><button class="admin-theme-toggle" id="admin-theme-toggle" onclick="toggleAdminTheme()" aria-label="Switch color theme"><i class="fa-solid fa-moon"></i></button><span style="font-size:12px;color:#a8a4b8;background:rgba(157,78,221,0.2);padding:5px 12px;border-radius:20px;border:1px solid rgba(255,215,0,0.2);">
      <i class="fa-solid fa-circle" style="color:#22c55e;font-size:8px;"></i> Online
    </span></div>
  </header>

  <div class="page-container">

    <!-- DASHBOARD -->
    <div id="dashboard" class="section active">
      <div class="stats-grid">
        <div class="stat-card"><div class="icon-box ib-purple"><i class="fa-solid fa-users"></i></div><div><span class="st-val" id="d-users">0</span><span>Total Users</span></div></div>
        <div class="stat-card"><div class="icon-box ib-green"><i class="fa-solid fa-wallet"></i></div><div><span class="st-val" id="d-dep">0</span><span>Total Deposits</span></div></div>
        <div class="stat-card"><div class="icon-box ib-red"><i class="fa-solid fa-money-bill-wave"></i></div><div><span class="st-val" id="d-with">0</span><span>Total Withdrawals</span></div></div>
        <div class="stat-card"><div class="icon-box ib-gold"><i class="fa-solid fa-hourglass-half"></i></div><div><span class="st-val" id="d-pending">0</span><span>Pending</span></div></div>
      </div>
    </div>

    <!-- DEPOSIT -->
    <div id="deposit" class="section">
      <div class="table-card">
        <div class="table-header"><span><i class="fa-solid fa-arrow-down" style="color:#22c55e;"></i> Pending Deposits</span></div>
        <div style="overflow-x:auto;">
          <table><thead><tr><th>UID</th><th>Method</th><th>Transaction ID</th><th>Amount</th><th>Action</th></tr></thead>
          <tbody id="dep-body"></tbody></table>
        </div>
      </div>
    </div>

    <!-- WITHDRAW -->
    <div id="withdraw" class="section">
      <div class="table-card">
        <div class="table-header"><span><i class="fa-solid fa-arrow-up" style="color:#ef4444;"></i> Pending Withdrawals</span></div>
        <div style="overflow-x:auto;">
          <table><thead><tr><th>UID</th><th>Method</th><th>Phone/Name</th><th>Amount</th><th>Action</th></tr></thead>
          <tbody id="with-body"></tbody></table>
        </div>
      </div>
    </div>

    <!-- USERS + DOWNLOAD -->
    <div id="users" class="section">
      <div class="table-card">
        <div class="table-header">
          <span><i class="fa-solid fa-users"></i> User Management</span>
          <button class="btn-action-gold" onclick="downloadAllUsers()" style="font-size:12px;padding:8px 16px;">
            <i class="fa-solid fa-download"></i> Download All (JSON)
          </button>
        </div>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>UID</th><th>Phone</th><th>Password</th><th>Wallet (D/W/B)</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody id="users-body"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- MAIN API -->
    <div id="mainapi" class="section">
      <div class="table-card" style="padding:25px;max-width:800px;margin-bottom:20px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-code"></i> Main API Management</h3>
        <div style="background:rgba(255,215,0,0.1);border-left:4px solid #FFD700;padding:15px;border-radius:10px;margin-bottom:20px;font-size:12px;color:#FFD700;">
          <i class="fa-solid fa-circle-info"></i> Main API သည် External Bot/Server များအတွက်။ <b>X-API-Key</b> header ဖြင့် အသုံးပြုပါ။
        </div>

        <label>Current API Key</label>
        <div style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;">
          <input type="text" id="current-api-key" class="form-control" readonly style="font-family:monospace;flex:1;min-width:200px;margin-bottom:0;">
          <button class="btn-action-blue" onclick="copyApiKey()" style="white-space:nowrap;padding:12px 18px;">
            <i class="fa-solid fa-copy"></i> Copy
          </button>
        </div>

        <label>New API Key (leave empty to keep current)</label>
        <input type="text" id="new-api-key" class="form-control" placeholder="Minimum 8 characters">
        <button class="btn-primary" onclick="changeApiKey()">
          <i class="fa-solid fa-save"></i> Change API Key
        </button>

        <div style="height:1px;background:rgba(157,78,221,0.2);margin:30px 0;"></div>

        <h4 style="color:#FFD700;margin-bottom:15px;font-size:14px;display:flex;align-items:center;gap:8px;">
          <i class="fa-solid fa-book"></i> API Endpoints
        </h4>
        <div style="background:rgba(10,5,20,0.9);border:1px solid rgba(157,78,221,0.3);border-radius:12px;padding:15px;font-family:monospace;font-size:11px;color:#00E5FF;line-height:1.9;overflow-x:auto;">
          <div><b style="color:#22c55e;">POST</b> /api/main/login      — Login</div>
          <div><b style="color:#3b82f6;">GET </b> /api/main/user/&lt;uid&gt; — User info</div>
          <div><b style="color:#22c55e;">POST</b> /api/main/balance    — Multi balance</div>
          <div><b style="color:#22c55e;">POST</b> /api/main/bet        — Bet</div>
          <div><b style="color:#22c55e;">POST</b> /api/main/bet-multi  — Multi bet</div>
          <div><b style="color:#22c55e;">POST</b> /api/main/deposit    — Deposit</div>
          <div><b style="color:#22c55e;">POST</b> /api/main/withdraw   — Withdraw</div>
          <div style="margin-top:10px;color:#a8a4b8;">Header: <b style="color:#FFD700;">X-API-Key: &lt;your-key&gt;</b></div>
        </div>
      </div>

      <div class="table-card">
        <div class="table-header">
          <span><i class="fa-solid fa-list"></i> API Request Logs</span>
          <button class="btn-action-blue" onclick="loadApiLogs()" style="font-size:11px;">
            <i class="fa-solid fa-sync"></i> Refresh
          </button>
        </div>
        <div style="overflow-x:auto;">
          <table>
            <thead><tr><th>Time</th><th>Endpoint</th><th>UID</th><th>IP</th></tr></thead>
            <tbody id="api-logs-body">
              <tr><td colspan="4" style="text-align:center;padding:20px;color:#666;">Loading...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- GAME CONTROL -->
    <div id="game" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-gamepad"></i> Real Game Control · Wingo + African Buffalo</h3>

        <div style="background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.25);border-radius:14px;padding:18px;margin-bottom:22px;">
          <h4 style="color:#FFD700;margin-bottom:8px;"><i class="fa-solid fa-buffalo"></i> African Buffalo RTP</h4>
          <p style="font-size:11px;color:#a8a4b8;margin-bottom:12px;">Global default for African Buffalo. A user-specific value can be set from Users + Download.</p>
          <div style="display:flex;gap:10px;align-items:end;">
            <div style="flex:1;"><label>Default RTP (0–100)</label><input type="number" id="af-global-rtp" class="form-control" min="0" max="100" step="0.1" value="96"></div>
            <button class="btn-action-gold" style="padding:12px 16px;white-space:nowrap;" onclick="saveAfricanBuffaloGlobalRtp()">Save RTP</button>
          </div>
          <div class="two-col" style="margin-top:14px;">
            <div><label>Room 1 Real RTP</label><input type="number" id="af-rtp-1" class="form-control" min="0" max="100" step="0.1" value="96"></div>
            <div><label>Room 2 Real RTP</label><input type="number" id="af-rtp-2" class="form-control" min="0" max="100" step="0.1" value="96"></div>
            <div><label>Room 3 Real RTP</label><input type="number" id="af-rtp-3" class="form-control" min="0" max="100" step="0.1" value="96"></div>
            <div><label>Room 4 Real RTP</label><input type="number" id="af-rtp-4" class="form-control" min="0" max="100" step="0.1" value="96"></div>
          </div>
          <p style="font-size:10px;color:#777;margin-top:8px;">The player-facing RTP text is randomized for display; these are the actual room controls used by the demo engine.</p>
          <label style="margin-top:14px;">African Buffalo Loading Logo</label>
          <div class="logo-upload-box" onclick="document.getElementById('af-logo-file').click()">
            <i class="fa-solid fa-cloud-arrow-up"></i>
            <p>Upload Buffalo logo (PNG/JPG)</p>
            <input type="file" id="af-logo-file" accept="image/*" onchange="uploadImage(this,'af-logo-preview')">
          </div>
          <img id="af-logo-preview" class="logo-preview" src="" style="display:none;">
          <div class="two-col" style="margin-top:8px;">
            <button class="btn-primary" onclick="saveAfricanBuffaloLogo()"><i class="fa-solid fa-save"></i> Save Buffalo Logo</button>
            <button class="btn-action-red" style="padding:13px;font-size:13px;" onclick="clearAfricanBuffaloLogo()"><i class="fa-solid fa-trash"></i> Clear</button>
          </div>
        </div>

        <label>Wingo Game Logo (Set)</label>
        <div class="logo-upload-box" onclick="document.getElementById('wingo-logo-file').click()">
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <p>Upload Wingo Logo (PNG/JPG)</p>
          <input type="file" id="wingo-logo-file" accept="image/*" onchange="uploadImage(this,'wingo-logo-preview')">
        </div>
        <img id="wingo-logo-preview" class="logo-preview" src="" style="display:none;">
        <div class="two-col" style="margin-bottom:20px;">
          <button class="btn-primary" onclick="saveWingoLogo()">
            <i class="fa-solid fa-save"></i> Save
          </button>
          <button class="btn-action-red" style="padding:13px;font-size:13px;" onclick="clearWingoLogo()">
            <i class="fa-solid fa-trash"></i> Clear
          </button>
        </div>

        <div style="height:1px;background:rgba(157,78,221,0.2);margin:20px 0;"></div>

        <label>Game Duration</label>
        <select id="gc-duration" class="form-control">
          <option value="30">Wingo 30s</option>
          <option value="60">Wingo 1m</option>
          <option value="180">Wingo 3m</option>
          <option value="300">Wingo 5m</option>
        </select>

        <label>Force Result (0-9)</label>
        <div class="three-col" style="grid-template-columns:repeat(5,1fr);margin-bottom:20px;">
          <button class="btn-action-purple" onclick="setNum(0)">0</button>
          <button class="btn-action-purple" onclick="setNum(1)">1</button>
          <button class="btn-action-purple" onclick="setNum(2)">2</button>
          <button class="btn-action-purple" onclick="setNum(3)">3</button>
          <button class="btn-action-purple" onclick="setNum(4)">4</button>
          <button class="btn-action-purple" onclick="setNum(5)">5</button>
          <button class="btn-action-purple" onclick="setNum(6)">6</button>
          <button class="btn-action-purple" onclick="setNum(7)">7</button>
          <button class="btn-action-purple" onclick="setNum(8)">8</button>
          <button class="btn-action-purple" onclick="setNum(9)">9</button>
        </div>
        <div style="color:#a8a4b8;margin-bottom:15px;font-size:13px;">
          Selected: <span id="sel-num" style="color:#FFD700;font-weight:bold;">None</span>
        </div>
        <button class="btn-primary" onclick="submitForcedResult()">
          <i class="fa-solid fa-bullseye"></i> Force Result
        </button>
      </div>
    </div>

    <!-- NOTIFICATIONS -->
    <div id="notifications" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-bell"></i> Send Notification</h3>
        <label>Target</label>
        <select id="notif-target" class="form-control" onchange="document.getElementById('notif-user-box').style.display=this.value==='personal'?'block':'none'">
          <option value="global">All Users</option>
          <option value="personal">Single User</option>
        </select>
        <div id="notif-user-box" style="display:none;">
          <label>User UID</label>
          <input type="text" id="notif-uid" class="form-control">
        </div>
        <label>Title</label>
        <input type="text" id="notif-title" class="form-control" placeholder="Title">
        <label>Message</label>
        <textarea id="notif-msg" class="form-control" rows="4" placeholder="Message"></textarea>
        <button class="btn-primary" onclick="sendNotif()">
          <i class="fa-solid fa-paper-plane"></i> Send
        </button>
      </div>
    </div>

    <!-- PAYMENT + LOGOS -->
    <div id="payment" class="section">
      <div class="table-card" style="padding:25px;max-width:700px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-credit-card"></i> KPay / Wave + Logos</h3>

        <!-- KPAY -->
        <div style="background:rgba(230,0,35,0.08);border-radius:14px;padding:20px;margin-bottom:20px;border-left:4px solid #e60023;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:15px;flex-wrap:wrap;">
            <div id="admin-kpay-logo-preview" style="width:60px;height:60px;border-radius:12px;background:#e60023;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:14px;overflow:hidden;flex-shrink:0;">
              KPay
            </div>
            <div>
              <strong style="font-size:14px;color:#fff;">KPay (Manual Approval)</strong>
              <p style="font-size:11px;color:#a8a4b8;margin-top:4px;">Admin approve မှ ငွေဝင်ပါမည်</p>
            </div>
          </div>

          <div class="two-col">
            <div>
              <label>Phone Number</label>
              <input type="text" id="kpay-phone" class="form-control" placeholder="09xxxxxxxxx">
            </div>
            <div>
              <label>Account Name</label>
              <input type="text" id="kpay-name" class="form-control" placeholder="Account holder name">
            </div>
          </div>

          <label>KPay Logo</label>
          <div class="logo-upload-box" onclick="document.getElementById('kpay-logo-file').click()">
            <i class="fa-solid fa-cloud-arrow-up"></i>
            <p>Upload KPay Logo</p>
            <input type="file" id="kpay-logo-file" accept="image/*" onchange="uploadImage(this,'kpay-logo-preview')">
          </div>
          <img id="kpay-logo-preview" class="logo-preview" src="" style="display:none;">
          <button class="btn-action-red" style="width:100%;padding:10px;margin-top:10px;" onclick="clearLogo('kpay-logo-preview')">
            <i class="fa-solid fa-trash"></i> Clear KPay Logo
          </button>
        </div>

        <!-- WAVE -->
        <div style="background:rgba(255,215,0,0.08);border-radius:14px;padding:20px;margin-bottom:20px;border-left:4px solid #FFD700;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:15px;flex-wrap:wrap;">
            <div id="admin-wave-logo-preview" style="width:60px;height:60px;border-radius:12px;background:linear-gradient(135deg,#FFD700,#FFA500);display:flex;align-items:center;justify-content:center;color:#1a0a2e;font-weight:900;font-size:14px;overflow:hidden;flex-shrink:0;">
              Wave
            </div>
            <div>
              <strong style="font-size:14px;color:#fff;">Wave Pay (Manual Approval)</strong>
              <p style="font-size:11px;color:#FFD700;margin-top:4px;">Admin approve မှ ငွေဝင်ပါမည်</p>
            </div>
          </div>

          <div class="two-col">
            <div>
              <label>Phone Number</label>
              <input type="text" id="wave-phone" class="form-control" value="09691835083" placeholder="09xxxxxxxxx">
            </div>
            <div>
              <label>Account Name</label>
              <input type="text" id="wave-name" class="form-control" placeholder="Account holder name">
            </div>
          </div>

          <label>Wave Logo</label>
          <div class="logo-upload-box" onclick="document.getElementById('wave-logo-file').click()">
            <i class="fa-solid fa-cloud-arrow-up"></i>
            <p>Upload Wave Logo</p>
            <input type="file" id="wave-logo-file" accept="image/*" onchange="uploadImage(this,'wave-logo-preview')">
          </div>
          <img id="wave-logo-preview" class="logo-preview" src="" style="display:none;">
          <button class="btn-action-red" style="width:100%;padding:10px;margin-top:10px;" onclick="clearLogo('wave-logo-preview')">
            <i class="fa-solid fa-trash"></i> Clear Wave Logo
          </button>
        </div>

        <div class="two-col">
          <div>
            <label>Min Deposit (Ks)</label>
            <input type="number" id="min-deposit" class="form-control" value="1000">
          </div>
          <div>
            <label>Min Withdraw (Ks)</label>
            <input type="number" id="min-withdraw" class="form-control" value="10000">
          </div>
        </div>

        <label>Support Link</label>
        <input type="text" id="support-link" class="form-control" placeholder="https://t.me/...">

        <button class="btn-primary" onclick="savePaymentSettings()">
          <i class="fa-solid fa-save"></i> Save All
        </button>
      </div>
    </div>

    <!-- SLIDER -->
    <div id="slider" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-image"></i> Add Slider</h3>
        <label>Image</label>
        <div class="logo-upload-box" onclick="document.getElementById('slider-img-file').click()">
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <p>Upload slider image</p>
          <input type="file" id="slider-img-file" accept="image/*" onchange="uploadSlider(this)">
        </div>
        <img id="slider-img-preview" class="slider-preview" src="" style="display:none;">
        <input type="hidden" id="slider-img-data">
        <label>Title (optional)</label>
        <input type="text" id="slider-title" class="form-control" placeholder="GAG2026">
        <label>Subtitle (optional)</label>
        <input type="text" id="slider-sub" class="form-control" placeholder="Play and win">
        <label>Link (optional)</label>
        <input type="text" id="slider-link" class="form-control">
        <button class="btn-primary" onclick="addSlider()">
          <i class="fa-solid fa-plus"></i> Add Slider
        </button>
      </div>
      <div id="slider-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;margin-top:20px;"></div>
    </div>

    <!-- BONUS -->
    <div id="bonus" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-gift"></i> Create Gift Code</h3>
        <div class="two-col">
          <input type="number" id="bonus-amt" class="form-control" placeholder="Amount (Ks)">
          <input type="number" id="bonus-limit" class="form-control" placeholder="Max users">
        </div>
        <button class="btn-primary" onclick="createBonus()">
          <i class="fa-solid fa-gift"></i> Create Code
        </button>
        <div id="bonus-result-box" style="margin-top:20px;background:rgba(10,5,20,0.9);padding:15px;border-radius:12px;display:none;text-align:center;border:1px solid rgba(255,215,0,0.3);">
          <span id="bonus-display" style="color:#FFD700;font-weight:bold;font-size:16px;letter-spacing:2px;word-break:break-all;font-family:'Orbitron',sans-serif;"></span>
        </div>
      </div>
      <div class="table-card">
        <div class="table-header">Active Codes</div>
        <table><tbody id="bonus-list"></tbody></table>
      </div>
    </div>

    <!-- APP CONFIG + BACKGROUNDS -->
    <div id="appconfig" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-cog"></i> App + Backgrounds</h3>

        <label>App Name</label>
        <input type="text" id="app-name" class="form-control" placeholder="GAG2026">

        <label>App Logo</label>
        <div class="logo-upload-box" onclick="document.getElementById('app-logo-file').click()">
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <p>Upload App Logo</p>
          <input type="file" id="app-logo-file" accept="image/*" onchange="uploadImage(this,'app-logo-preview')">
        </div>
        <img id="app-logo-preview" class="logo-preview" src="" style="display:none;">

        <label>Login Background</label>
        <div class="logo-upload-box" onclick="document.getElementById('login-bg-file').click()">
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <p>Upload Login Background</p>
          <input type="file" id="login-bg-file" accept="image/*" onchange="uploadImage(this,'login-bg-preview')">
        </div>
        <img id="login-bg-preview" class="slider-preview" src="" style="display:none;">

        <label style="color:#00E5FF;font-weight:700;">
          <i class="fa-solid fa-globe"></i> Website Background (Full Page)
        </label>
        <div class="logo-upload-box" onclick="document.getElementById('page-bg-file').click()" style="border-color:#00E5FF;">
          <i class="fa-solid fa-cloud-arrow-up" style="color:#00E5FF;"></i>
          <p>Upload Website Background<br><small style="color:#666;">(Shows on entire site)</small></p>
          <input type="file" id="page-bg-file" accept="image/*" onchange="uploadImage(this,'page-bg-preview')">
        </div>
        <img id="page-bg-preview" class="slider-preview" src="" style="display:none;">
        <button class="btn-action-red" style="width:100%;padding:10px;margin-bottom:15px;" onclick="clearPageBg()">
          <i class="fa-solid fa-trash"></i> Clear Website Background
        </button>

        <label style="color:#9D4EDD;font-weight:700;">
          <i class="fa-solid fa-gamepad"></i> Wingo Game Background
        </label>
        <div class="logo-upload-box" onclick="document.getElementById('wingo-bg-file').click()" style="border-color:#9D4EDD;">
          <i class="fa-solid fa-cloud-arrow-up" style="color:#9D4EDD;"></i>
          <p>Upload Wingo Game Background<br><small style="color:#666;">(Shows in Wingo game)</small></p>
          <input type="file" id="wingo-bg-file" accept="image/*" onchange="uploadImage(this,'wingo-bg-preview')">
        </div>
        <img id="wingo-bg-preview" class="slider-preview" src="" style="display:none;">
        <button class="btn-action-red" style="width:100%;padding:10px;margin-bottom:15px;" onclick="clearWingoBg()">
          <i class="fa-solid fa-trash"></i> Clear Wingo Background
        </button>

        <label>Ingame Background (Slider default)</label>
        <div class="logo-upload-box" onclick="document.getElementById('ingame-bg-file').click()">
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <p>Upload Ingame Background</p>
          <input type="file" id="ingame-bg-file" accept="image/*" onchange="uploadImage(this,'ingame-bg-preview')">
        </div>
        <img id="ingame-bg-preview" class="slider-preview" src="" style="display:none;">

        <label>Signup Bonus (Ks)</label>
        <input type="number" id="signup-bonus" class="form-control" value="5000">
        <label>Referral Bonus (Ks)</label>
        <input type="number" id="referral-bonus" class="form-control" value="2000">
        <label style="margin-top:18px;color:#0f766e;font-weight:700;">UI Icon Images</label>
        <p style="font-size:12px;color:#64748b;margin-bottom:10px;">Icon တစ်ခုချင်းစီအတွက် ပုံရွေးပါ။ မရွေးထားတဲ့ icon က မူရင်း icon အတိုင်း ဆက်ပြပါမယ်။</p>
        <div class="icon-pack-item" style="margin-bottom:10px;text-align:left;"><span>Generic fallback (ကျန် icon အားလုံး)</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'generic')"><img id="icon-preview-generic"></div>
        <div class="remove-bg-tool">
          <b>Background Remove Tool</b>
          <small>ပုံထည့်ပြီး Remove ကိုနှိပ်ပါ။ အနားက uniform background ကို transparent PNG ပြောင်းပေးပါမယ်။</small>
          <input type="file" id="remove-bg-file" accept="image/*" onchange="uploadRemoveBg(this)">
          <img id="remove-bg-preview" style="display:none;">
          <button type="button" class="btn-primary" onclick="processRemoveBg()">Remove Background</button>
        </div>
        <div class="icon-pack-grid">
          <div class="icon-pack-item"><span>Home</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'home')"><img id="icon-preview-home"></div>
          <div class="icon-pack-item"><span>Wallet</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'wallet')"><img id="icon-preview-wallet"></div>
          <div class="icon-pack-item"><span>Bonus</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'bonus')"><img id="icon-preview-bonus"></div>
          <div class="icon-pack-item"><span>History</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'history')"><img id="icon-preview-history"></div>
          <div class="icon-pack-item"><span>Rules</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'rules')"><img id="icon-preview-rules"></div>
          <div class="icon-pack-item"><span>Support</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'support')"><img id="icon-preview-support"></div>
          <div class="icon-pack-item"><span>Menu</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'menu')"><img id="icon-preview-menu"></div>
          <div class="icon-pack-item"><span>Bell</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'bell')"><img id="icon-preview-bell"></div>
          <div class="icon-pack-item"><span>Deposit</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'deposit')"><img id="icon-preview-deposit"></div>
          <div class="icon-pack-item"><span>Withdraw</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'withdraw')"><img id="icon-preview-withdraw"></div>
          <div class="icon-pack-item"><span>Info</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'info')"><img id="icon-preview-info"></div>
          <div class="icon-pack-item"><span>Close</span><input type="file" accept="image/*" onchange="uploadIconPack(this,'close')"><img id="icon-preview-close"></div>
        </div>
        <label style="margin-top:16px;">Website Rules Text (optional)</label>
        <textarea id="rules-text" class="form-control" rows="4" placeholder="Rules text shown on the public rules page"></textarea>
        <button class="btn-primary" onclick="saveAppConfig()">
          <i class="fa-solid fa-save"></i> Save All
        </button>
      </div>
    </div>

    <!-- ADMIN CRED -->
    <div id="admincred" class="section">
      <div class="table-card" style="padding:25px;max-width:600px;">
        <h3 class="section-title-admin"><i class="fa-solid fa-user-shield"></i> Admin Credentials</h3>
        <label>Current Username</label>
        <input type="text" id="cur-admin-username" class="form-control" readonly>
        <label>New Username</label>
        <input type="text" id="new-admin-username" class="form-control" placeholder="New username">
        <label>New Password</label>
        <input type="password" id="new-admin-password" class="form-control" placeholder="New password">
        <label>Confirm Password</label>
        <input type="password" id="new-admin-password-confirm" class="form-control" placeholder="Confirm password">
        <label>Current Password</label>
        <input type="password" id="cur-admin-password" class="form-control" placeholder="Current password">
        <button class="btn-primary" onclick="changeAdminCreds()">
          <i class="fa-solid fa-key"></i> Change
        </button>
      </div>
    </div>

  </div>
</div>

<!-- TXN MODAL -->
<div class="modal-overlay" id="txnModal">
  <div class="modal-box">
    <div class="modal-header"><span id="m-title">Manage</span><i class="fa-solid fa-xmark" onclick="closeModal('txnModal')" style="cursor:pointer;"></i></div>
    <div class="modal-body">
      <div class="info-row"><span>User ID:</span><span id="m-uid">---</span></div>
      <div class="info-row"><span>Method:</span><span id="m-method">---</span></div>
      <div class="info-row"><span>Amount:</span><span id="m-amt" style="color:#FFD700;">Ks 0</span></div>
      <div class="info-row"><span>Details:</span><span id="m-details" style="font-size:12px;">---</span></div>
    </div>
    <div class="modal-footer">
      <button class="m-btn m-btn-reject" onclick="processTxn('reject')"><i class="fa-solid fa-xmark"></i> Reject</button>
      <button class="m-btn m-btn-approve" onclick="processTxn('approve')"><i class="fa-solid fa-check"></i> Approve</button>
    </div>
  </div>
</div>

<!-- USER MODAL -->
<div class="modal-overlay" id="userModal">
  <div class="modal-box">
    <div class="modal-header"><span>User Wallet</span><i class="fa-solid fa-xmark" onclick="closeModal('userModal')" style="cursor:pointer;"></i></div>
    <div class="modal-body">
      <div class="info-row"><span>UID:</span><span id="u-uid">---</span></div>
      <div class="info-row"><span>Deposit:</span><span id="u-bal-d">Ks 0</span></div>
      <div class="info-row"><span>Winning:</span><span id="u-bal-w">Ks 0</span></div>
      <div class="info-row"><span>Bonus:</span><span id="u-bal-b">Ks 0</span></div>
      <div class="info-row"><span>Total Deposit:</span><span id="u-total-dep">Ks 0</span></div>
      <div class="info-row"><span>Total Bet:</span><span id="u-total-bet">Ks 0</span></div>
      <label>Action</label>
      <select id="u-action" class="form-control">
        <option value="add">Add (Credit)</option>
        <option value="deduct">Deduct (Debit)</option>
      </select>
      <label>Wallet Type</label>
      <select id="u-wallet-type" class="form-control">
        <option value="deposit">Deposit Wallet</option>
        <option value="winning">Winning Wallet</option>
        <option value="bonus">Bonus Wallet</option>
      </select>
      <label>Amount</label>
      <input type="number" id="u-amount" class="form-control" placeholder="Example: 10000">

      <label>African Buffalo RTP (0–100)</label>
      <div style="display:flex;gap:8px;align-items:center;">
        <input type="number" id="u-af-rtp" class="form-control" min="0" max="100" step="0.1" placeholder="Use global default" style="margin-bottom:0;">
        <button class="btn-action-gold" style="padding:11px 14px;white-space:nowrap;" onclick="saveUserAfricanBuffaloRtp()">Save RTP</button>
      </div>
      <button class="btn-action-blue" style="width:100%;padding:11px;font-size:12px;margin-top:12px;" onclick="loadAfricanBuffaloHistory(editUser.uid)">
        <i class="fa-solid fa-chart-line"></i> View African Buffalo History
      </button>
      <button class="btn-action-purple" style="width:100%;padding:11px;font-size:12px;margin-top:8px;" onclick="downloadAfricanBuffaloHistory(editUser.uid)">
        <i class="fa-solid fa-file-arrow-down"></i> Download Buffalo History JSON
      </button>
      <div id="u-af-history" style="max-height:180px;overflow:auto;margin-top:10px;font-size:11px;color:#a8a4b8;"></div>
      
      <div style="height:1px;background:rgba(157,78,221,0.2);margin:20px 0;"></div>
      
      <button class="btn-action-purple" style="width:100%;padding:12px;font-size:13px;margin-bottom:10px;" onclick="downloadUserJSON()">
        <i class="fa-solid fa-download"></i> Download User JSON (History)
      </button>
      <button class="m-btn m-btn-ban" id="btn-block" style="width:100%;margin-top:10px;" onclick="toggleBlock()">
        <i class="fa-solid fa-ban"></i> Block User
      </button>
    </div>
    <div class="modal-footer">
      <button class="m-btn m-btn-approve" onclick="updateUserBalance()">
        <i class="fa-solid fa-check"></i> Update Balance
      </button>
    </div>
  </div>
</div>

<script>
const API = window.location.origin;
let curTxn = {};
let editUser = {};
let selForcedNum = null;
let iconPackDraft = {};

function fmt(n){return Number(n).toLocaleString('en-US');}

function toggleSidebar(){
  document.getElementById('sidebar').classList.toggle('active');
  document.getElementById('sidebarOverlay').classList.toggle('active');
}

function showSection(id,el){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(el){
    document.querySelectorAll('.menu-item').forEach(m=>m.classList.remove('active'));
    el.classList.add('active');
  }
  document.getElementById('page-title').innerText = id.toUpperCase();
  if(window.innerWidth <= 768){
    document.getElementById('sidebar').classList.remove('active');
    document.getElementById('sidebarOverlay').classList.remove('active');
  }
  if(id==='dashboard') loadDashboard();
  if(id==='deposit') loadDeposits();
  if(id==='withdraw') loadWithdrawals();
  if(id==='users') loadUsers();
  if(id==='payment') loadPaymentSettings();
  if(id==='slider') loadSliders();
  if(id==='bonus') loadBonusCodes();
  if(id==='appconfig') loadAppConfig();
  if(id==='game') loadGameSettings();
  if(id==='admincred') loadAdminCreds();
  if(id==='mainapi') loadApiKey();
}

function closeModal(id){document.getElementById(id).classList.remove('active');}
function logoutAdmin(){window.location.href='/admin/logout';}

function uploadImage(input,previewId){
  if(input.files && input.files[0]){
    const reader = new FileReader();
    reader.onload = function(e){
      const preview = document.getElementById(previewId);
      if(preview){preview.src = e.target.result;preview.style.display='block';}
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function uploadIconPack(input,key){
  if(!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = function(e){
    iconPackDraft[key] = e.target.result;
    const preview = document.getElementById('icon-preview-' + key);
    if(preview){preview.src=e.target.result;preview.style.display='block';}
  };
  reader.readAsDataURL(input.files[0]);
}

let removeBgImageData = '';
function uploadRemoveBg(input){
  if(!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = e => { removeBgImageData=e.target.result; const p=document.getElementById('remove-bg-preview'); p.src=removeBgImageData; p.style.display='block'; };
  reader.readAsDataURL(input.files[0]);
}
async function processRemoveBg(){
  if(!removeBgImageData){alert('Choose an image first');return;}
  const r = await fetch(`${API}/api/admin/remove-background`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:removeBgImageData})});
  const d = await r.json();
  if(!d.success){alert(d.message || 'Background removal failed');return;}
  removeBgImageData=d.image;
  const p=document.getElementById('remove-bg-preview'); p.src=d.image; p.style.display='block';
  iconPackDraft.generic=d.image;
  const generic=document.getElementById('icon-preview-generic'); generic.src=d.image; generic.style.display='block';
  alert('Transparent image ready. Save All to use it as the generic icon.');
}

function renderIconPack(pack){
  iconPackDraft = Object.assign({}, pack || {});
  Object.entries(iconPackDraft).forEach(([key,src])=>{
    const preview = document.getElementById('icon-preview-' + key);
    if(preview && src){preview.src=src;preview.style.display='block';}
  });
}

function uploadSlider(input){
  if(input.files && input.files[0]){
    const reader = new FileReader();
    reader.onload = function(e){
      document.getElementById('slider-img-preview').src = e.target.result;
      document.getElementById('slider-img-preview').style.display = 'block';
      document.getElementById('slider-img-data').value = e.target.result;
    };
    reader.readAsDataURL(input.files[0]);
  }
}

async function loadAdminCreds(){
  const r = await fetch(`${API}/api/admin/current-creds`);
  const d = await r.json();
  if(d.success) document.getElementById('cur-admin-username').value = d.username;
}

async function changeAdminCreds(){
  const newUser = document.getElementById('new-admin-username').value.trim();
  const newPass = document.getElementById('new-admin-password').value;
  const conf = document.getElementById('new-admin-password-confirm').value;
  const curPass = document.getElementById('cur-admin-password').value;
  if(!newUser && !newPass){alert('Enter new username or password');return;}
  if(newPass && newPass !== conf){alert('Passwords do not match');return;}
  if(!curPass){alert('Enter current password');return;}
  const r = await fetch(`${API}/api/admin/change-creds`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({currentPassword:curPass,newUsername:newUser,newPassword:newPass})
  });
  const d = await r.json();
  if(d.success){alert('Changed successfully');loadAdminCreds();}
  else alert(d.message || 'Failed');
}

async function loadGameSettings(){
  const r = await fetch(`${API}/api/settings`);
  const d = await r.json();
  const ar = await fetch(`${API}/api/admin/african-buffalo/settings`);
  const ad = await ar.json();
  if(ad.success){
    document.getElementById('af-global-rtp').value = ad.rtp;
    for(let i=1;i<=4;i++) document.getElementById(`af-rtp-${i}`).value = (ad.rooms && ad.rooms[String(i)] !== undefined) ? ad.rooms[String(i)] : ad.rtp;
  }
  if(d.wingo_logo){
    document.getElementById('wingo-logo-preview').src = d.wingo_logo;
    document.getElementById('wingo-logo-preview').style.display = 'block';
  }
  if(d.african_buffalo_logo){
    document.getElementById('af-logo-preview').src = d.african_buffalo_logo;
    document.getElementById('af-logo-preview').style.display = 'block';
  }
}

async function saveAfricanBuffaloGlobalRtp(){
  const rtp = Math.max(0, Math.min(100, Number(document.getElementById('af-global-rtp').value) || 0));
  const body = {rtp};
  for(let i=1;i<=4;i++) body[`room_${i}`] = Math.max(0, Math.min(100, Number(document.getElementById(`af-rtp-${i}`).value) || rtp));
  const r = await fetch(`${API}/api/admin/african-buffalo/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json(); alert(d.success ? 'African Buffalo global RTP saved' : (d.message || 'Failed'));
}

async function saveAfricanBuffaloLogo(){
  const preview = document.getElementById('af-logo-preview');
  if(!preview.src || preview.style.display === 'none'){alert('Choose a Buffalo logo first');return;}
  const r = await fetch(`${API}/api/admin/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({african_buffalo_logo:preview.src})});
  const d = await r.json(); alert(d.success ? 'African Buffalo logo saved' : 'Failed');
}

async function clearAfricanBuffaloLogo(){
  if(!confirm('Clear African Buffalo logo?')) return;
  const preview = document.getElementById('af-logo-preview');
  preview.src=''; preview.style.display='none';
  await fetch(`${API}/api/admin/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({african_buffalo_logo:''})});
  alert('Cleared');
}

async function saveWingoLogo(){
  const preview = document.getElementById('wingo-logo-preview');
  if(!preview.src || preview.style.display === 'none'){alert('Choose logo first');return;}
  await fetch(`${API}/api/admin/settings`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({wingo_logo:preview.src})
  });
  alert('Wingo logo saved');
}

async function clearWingoLogo(){
  if(!confirm('Clear Wingo logo?')) return;
  await fetch(`${API}/api/admin/settings`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({wingo_logo:''})
  });
  document.getElementById('wingo-logo-preview').src = '';
  document.getElementById('wingo-logo-preview').style.display = 'none';
  alert('Cleared');
}

function setNum(n){selForcedNum = n;document.getElementById('sel-num').innerText = n;}

async function submitForcedResult(){
  if(selForcedNum === null){alert('Choose a number');return;}
  const dur = parseInt(document.getElementById('gc-duration').value);
  await fetch(`${API}/api/admin/force-result`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({duration:dur,number:selForcedNum})
  });
  alert('Forced result set');
  selForcedNum = null;
  document.getElementById('sel-num').innerText = 'None';
}

async function loadDashboard(){
  const r = await fetch(`${API}/api/admin/dashboard`);
  const d = await r.json();
  document.getElementById('d-users').innerText = d.total_users;
  document.getElementById('d-dep').innerText = fmt(d.total_deposits);
  document.getElementById('d-with').innerText = fmt(d.total_withdrawals);
  document.getElementById('d-pending').innerText = d.pending;
}

async function loadDeposits(){
  const r = await fetch(`${API}/api/admin/deposits`);
  const d = await r.json();
  let html = '';
  d.deposits.forEach(x=>{
    const mb = x.method==='wave'?'<span class="badge" style="background:rgba(255,215,0,0.15);color:#FFD700;">Wave</span>':'<span class="badge" style="background:rgba(230,0,35,0.15);color:#ff4757;">KPay</span>';
    html += `<tr><td>${x.uid}</td><td>${mb}</td><td style="font-family:monospace;font-size:11px;">${x.utr}</td><td style="color:#22c55e;font-weight:bold;">Ks ${fmt(x.amount)}</td>
    <td><button class="btn-action-green" onclick='openTxn(${JSON.stringify(x)},"dep")'>Manage</button></td></tr>`;
  });
  document.getElementById('dep-body').innerHTML = html || '<tr><td colspan="5" style="text-align:center;padding:20px;color:#666;">No pending deposits</td></tr>';
}

async function loadWithdrawals(){
  const r = await fetch(`${API}/api/admin/withdrawals`);
  const d = await r.json();
  let html = '';
  d.withdrawals.forEach(x=>{
    const mb = x.method==='wave'?'<span class="badge" style="background:rgba(255,215,0,0.15);color:#FFD700;">Wave</span>':'<span class="badge" style="background:rgba(230,0,35,0.15);color:#ff4757;">KPay</span>';
    html += `<tr><td>${x.uid}</td><td>${mb}</td><td>${x.phone||'-'}<br><small style="color:#888;">${x.name||''}</small></td><td style="color:#ef4444;font-weight:bold;">Ks ${fmt(x.amount)}</td>
    <td><button class="btn-action-red" onclick='openTxn(${JSON.stringify(x)},"with")'>Manage</button></td></tr>`;
  });
  document.getElementById('with-body').innerHTML = html || '<tr><td colspan="5" style="text-align:center;padding:20px;color:#666;">No pending withdrawals</td></tr>';
}

function openTxn(x,type){
  curTxn = {...x,type};
  document.getElementById('m-title').innerText = type==='dep'?'Manage Deposit':'Manage Withdrawal';
  document.getElementById('m-uid').innerText = x.uid;
  document.getElementById('m-method').innerText = (x.method||'kpay').toUpperCase();
  document.getElementById('m-amt').innerText = 'Ks ' + fmt(x.amount);
  document.getElementById('m-details').innerText = x.utr || x.phone || '-';
  document.getElementById('txnModal').classList.add('active');
}

async function processTxn(action){
  const r = await fetch(`${API}/api/admin/process-txn`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({...curTxn,action})
  });
  const d = await r.json();
  if(d.success){
    alert('Processed');
    closeModal('txnModal');
    loadDeposits();loadWithdrawals();loadDashboard();
  }
}

async function loadUsers(){
  const r = await fetch(`${API}/api/admin/users`);
  const d = await r.json();
  let html = '';
  d.users.forEach(u=>{
    const w = u.wallet || {};
    html += `<tr>
      <td>${u.uid}</td>
      <td>${u.contact}</td>
      <td>${u.password}</td>
      <td style="font-size:11px;">D:${fmt(w.deposit||0)} | W:${fmt(w.winning||0)} | B:${fmt(w.bonus||0)}</td>
      <td>${u.isBanned?'<span class="bg-banned">BANNED</span>':'<span class="badge bg-success">ACTIVE</span>'}</td>
      <td style="white-space:nowrap;">
        <button class="btn-action-blue" onclick='editUserWallet(${JSON.stringify(u)})'>Manage</button>
        <button class="btn-action-purple" onclick="downloadSingleUser('${u.uid}')" title="Download JSON">
          <i class="fa-solid fa-download"></i>
        </button>
      </td>
    </tr>`;
  });
  document.getElementById('users-body').innerHTML = html || '<tr><td colspan="6" style="text-align:center;padding:20px;color:#666;">No users</td></tr>';
}

function editUserWallet(u){
  editUser = u;
  const w = u.wallet || {};
  document.getElementById('u-uid').innerText = u.uid;
  document.getElementById('u-bal-d').innerText = 'Ks ' + fmt(w.deposit||0);
  document.getElementById('u-bal-w').innerText = 'Ks ' + fmt(w.winning||0);
  document.getElementById('u-bal-b').innerText = 'Ks ' + fmt(w.bonus||0);
  document.getElementById('u-total-dep').innerText = 'Ks ' + fmt(u.totalDeposit||0);
  document.getElementById('u-total-bet').innerText = 'Ks ' + fmt(u.totalBet||0);
  document.getElementById('btn-block').innerHTML = u.isBanned?'<i class="fa-solid fa-check"></i> Unblock User':'<i class="fa-solid fa-ban"></i> Block User';
  document.getElementById('btn-block').style.background = u.isBanned?'linear-gradient(135deg,#22c55e,#16a34a)':'linear-gradient(135deg,#ef4444,#dc2626)';
  document.getElementById('u-amount').value = '';
  document.getElementById('u-af-rtp').value = u.africanBuffaloRtp ?? '';
  document.getElementById('u-af-history').innerHTML = '<span style="color:#666;">Click View History to load African Buffalo spins.</span>';
  document.getElementById('userModal').classList.add('active');
}

async function saveUserAfricanBuffaloRtp(){
  const rtp = document.getElementById('u-af-rtp').value;
  if(rtp === ''){alert('Enter an RTP value');return;}
  const r = await fetch(`${API}/api/admin/african-buffalo/user-rtp`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:editUser.uid,rtp:Number(rtp)})});
  const d = await r.json();
  if(d.success){editUser.africanBuffaloRtp=d.rtp;alert('User RTP saved');loadUsers();}else alert(d.message || 'Failed');
}

async function loadAfricanBuffaloHistory(uid){
  const box = document.getElementById('u-af-history');
  box.innerHTML = 'Loading...';
  const r = await fetch(`${API}/api/admin/african-buffalo/history/${uid}`);
  const d = await r.json();
  if(!d.success || !d.history.length){box.innerHTML='<span style="color:#666;">No African Buffalo history yet.</span>';return;}
  box.innerHTML = '<div style="display:grid;gap:5px;">' + d.history.slice(0,20).map(h=>`<div style="display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid rgba(157,78,221,.15);padding:5px 0;"><span>${new Date(h.timestamp).toLocaleString()}</span><span>Bet ${fmt(h.bet)} / Win ${fmt(h.win)} / RTP ${h.target_rtp}%</span></div>`).join('') + '</div>';
}

async function downloadAfricanBuffaloHistory(uid){
  const r = await fetch(`${API}/api/admin/african-buffalo/history/${uid}`);
  const d = await r.json();
  if(!d.success){alert('Failed to load history');return;}
  downloadJSONFile({game:'African Buffalo',uid,exported_at:new Date().toISOString(),history:d.history},`AfricanBuffalo_${uid}_${new Date().toISOString().slice(0,10)}.json`);
}

async function updateUserBalance(){
  const action = document.getElementById('u-action').value;
  const wallet = document.getElementById('u-wallet-type').value;
  const amt = Number(document.getElementById('u-amount').value);
  if(!amt || amt <= 0){alert('Enter valid amount');return;}
  const r = await fetch(`${API}/api/admin/user-balance`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({uid:editUser.uid,action,wallet,amount:amt})
  });
  const d = await r.json();
  if(d.success){alert('Updated');closeModal('userModal');loadUsers();}
}

async function toggleBlock(){
  if(!confirm('Are you sure?')) return;
  await fetch(`${API}/api/admin/toggle-block`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({uid:editUser.uid})
  });
  closeModal('userModal');
  loadUsers();
}

// ============ DOWNLOAD JSON FEATURES ============
function buildUserJSON(user, deps, withs, bets) {
  const userDeps = deps.filter(d => d.uid === user.uid);
  const userWiths = withs.filter(w => w.uid === user.uid);
  const userBets = bets.filter(b => b.uid === user.uid);
  const totalDeposit = userDeps.filter(d=>d.status==='success').reduce((s,d)=>s+(d.amount||0),0);
  const totalWithdraw = userWiths.filter(w=>w.status==='success').reduce((s,w)=>s+(w.amount||0),0);
  const totalBet = userBets.reduce((s,b)=>s+(b.amount||0),0);
  const totalWin = userBets.filter(b=>b.status==='win').reduce((s,b)=>s+(b.payout||0),0);
  return {
    exported_at: new Date().toISOString(),
    game: "GAG2026",
    user_info: {
      uid: user.uid,
      name: user.name,
      contact: user.contact,
      password: user.password,
      wallet: user.wallet,
      hasDeposited: user.hasDeposited || false,
      isBanned: user.isBanned || false,
      totalDeposit: user.totalDeposit || 0,
      totalBet: user.totalBet || 0,
      createdAt: user.createdAt
    },
    summary: {
      total_deposits_count: userDeps.length,
      total_deposits_amount: totalDeposit,
      total_withdrawals_count: userWiths.length,
      total_withdrawals_amount: totalWithdraw,
      total_bets_count: userBets.length,
      total_bets_amount: totalBet,
      total_wins_amount: totalWin
    },
    deposits: userDeps.sort((a,b)=>new Date(b.date)-new Date(a.date)),
    withdrawals: userWiths.sort((a,b)=>new Date(b.date)-new Date(a.date)),
    bets: userBets.sort((a,b)=>new Date(b.timestamp)-new Date(a.timestamp)).slice(0,500)
  };
}

function downloadJSONFile(data, filename){
  const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function downloadSingleUser(uid){
  try{
    const r = await fetch(`${API}/api/admin/user-export/${uid}`);
    const d = await r.json();
    if(!d.success){alert('Failed');return;}
    const filename = `GAG2026_User_${uid}_${new Date().toISOString().slice(0,10)}.json`;
    downloadJSONFile(d.data, filename);
    alert(`Downloaded ${filename}`);
  }catch(e){alert('Error: ' + e.message);}
}

async function downloadUserJSON(){
  if(!editUser.uid){alert('No user selected');return;}
  await downloadSingleUser(editUser.uid);
}

async function downloadAllUsers(){
  if(!confirm('Download ALL users data as JSON?')) return;
  try{
    const r = await fetch(`${API}/api/admin/export-all`);
    const d = await r.json();
    if(!d.success){alert('Failed');return;}
    const filename = `GAG2026_AllUsers_${new Date().toISOString().slice(0,10)}.json`;
    downloadJSONFile(d.data, filename);
    alert(`Downloaded ${filename}\nTotal users: ${d.data.total_users}`);
  }catch(e){alert('Error: ' + e.message);}
}

async function sendNotif(){
  const r = await fetch(`${API}/api/admin/notification`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      type:document.getElementById('notif-target').value,
      uid:document.getElementById('notif-uid').value,
      title:document.getElementById('notif-title').value,
      message:document.getElementById('notif-msg').value
    })
  });
  const d = await r.json();
  alert(d.success?'Sent':'Failed');
}

async function loadPaymentSettings(){
  const r = await fetch(`${API}/api/settings`);
  const d = await r.json();
  document.getElementById('kpay-phone').value = d.kpay_phone || '';
  document.getElementById('kpay-name').value = d.kpay_name || '';
  document.getElementById('wave-phone').value = d.wave_phone || '09691835083';
  document.getElementById('wave-name').value = d.wave_name || '';
  document.getElementById('min-deposit').value = d.min_deposit || 1000;
  document.getElementById('min-withdraw').value = d.min_withdraw || 10000;
  document.getElementById('support-link').value = d.support_link || '';

  if(d.kpay_logo){
    const kp = document.getElementById('kpay-logo-preview');
    kp.src = d.kpay_logo;
    kp.style.display = 'block';
    document.getElementById('admin-kpay-logo-preview').innerHTML = `<img src="${d.kpay_logo}" style="width:100%;height:100%;object-fit:contain;">`;
  } else {
    document.getElementById('admin-kpay-logo-preview').innerHTML = 'KPay';
  }

  if(d.wave_logo){
    const wp = document.getElementById('wave-logo-preview');
    wp.src = d.wave_logo;
    wp.style.display = 'block';
    document.getElementById('admin-wave-logo-preview').innerHTML = `<img src="${d.wave_logo}" style="width:100%;height:100%;object-fit:contain;">`;
  } else {
    document.getElementById('admin-wave-logo-preview').innerHTML = 'Wave';
  }
}

async function savePaymentSettings(){
  const body = {
    kpay_phone: document.getElementById('kpay-phone').value,
    kpay_name: document.getElementById('kpay-name').value,
    wave_phone: document.getElementById('wave-phone').value,
    wave_name: document.getElementById('wave-name').value,
    min_deposit: parseInt(document.getElementById('min-deposit').value),
    min_withdraw: parseInt(document.getElementById('min-withdraw').value),
    support_link: document.getElementById('support-link').value
  };
  const kp = document.getElementById('kpay-logo-preview');
  const wp = document.getElementById('wave-logo-preview');
  if(kp && kp.src && kp.style.display !== 'none' && kp.src.startsWith('data:')){body.kpay_logo = kp.src;}
  if(wp && wp.src && wp.style.display !== 'none' && wp.src.startsWith('data:')){body.wave_logo = wp.src;}
  try{
    const r = await fetch(`${API}/api/admin/settings`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if(d.success){alert('Saved');loadPaymentSettings();}
    else alert('Failed');
  }catch(e){alert('Error: ' + e.message);}
}

function clearLogo(previewId){
  if(!confirm('Clear logo?')) return;
  const el = document.getElementById(previewId);
  el.src = '';
  el.style.display = 'none';
  if(previewId === 'kpay-logo-preview'){
    document.getElementById('admin-kpay-logo-preview').innerHTML = 'KPay';
    fetch(`${API}/api/admin/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify({kpay_logo:''})});
  }
  if(previewId === 'wave-logo-preview'){
    document.getElementById('admin-wave-logo-preview').innerHTML = 'Wave';
    fetch(`${API}/api/admin/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify({wave_logo:''})});
  }
  alert('Cleared');
}

async function loadAppConfig(){
  const r = await fetch(`${API}/api/settings`);
  const d = await r.json();
  document.getElementById('app-name').value = d.app_name || '';
  document.getElementById('signup-bonus').value = d.signup_bonus || 5000;
  document.getElementById('referral-bonus').value = d.referral_bonus || 2000;
  document.getElementById('rules-text').value = d.rules_text || '';
  renderIconPack(d.icon_pack || {});
  if(d.app_logo){document.getElementById('app-logo-preview').src = d.app_logo;document.getElementById('app-logo-preview').style.display = 'block';}
  if(d.login_bg){document.getElementById('login-bg-preview').src = d.login_bg;document.getElementById('login-bg-preview').style.display = 'block';}
  if(d.ingame_bg){document.getElementById('ingame-bg-preview').src = d.ingame_bg;document.getElementById('ingame-bg-preview').style.display = 'block';}
  if(d.page_bg){document.getElementById('page-bg-preview').src = d.page_bg;document.getElementById('page-bg-preview').style.display = 'block';}
  if(d.wingo_bg){document.getElementById('wingo-bg-preview').src = d.wingo_bg;document.getElementById('wingo-bg-preview').style.display = 'block';}
}

async function saveAppConfig(){
  const body = {
    app_name: document.getElementById('app-name').value,
    signup_bonus: parseInt(document.getElementById('signup-bonus').value),
    referral_bonus: parseInt(document.getElementById('referral-bonus').value),
    rules_text: document.getElementById('rules-text').value,
    icon_pack: iconPackDraft
  };
  const al = document.getElementById('app-logo-preview');
  const lb = document.getElementById('login-bg-preview');
  const ib = document.getElementById('ingame-bg-preview');
  const pb = document.getElementById('page-bg-preview');
  const wb = document.getElementById('wingo-bg-preview');
  if(al && al.src && al.style.display !== 'none' && al.src.startsWith('data:')) body.app_logo = al.src;
  if(lb && lb.src && lb.style.display !== 'none' && lb.src.startsWith('data:')) body.login_bg = lb.src;
  if(ib && ib.src && ib.style.display !== 'none' && ib.src.startsWith('data:')) body.ingame_bg = ib.src;
  if(pb && pb.src && pb.style.display !== 'none' && pb.src.startsWith('data:')) body.page_bg = pb.src;
  if(wb && wb.src && wb.style.display !== 'none' && wb.src.startsWith('data:')) body.wingo_bg = wb.src;
  await fetch(`${API}/api/admin/settings`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  alert('Saved');
}

async function clearPageBg(){
  if(!confirm('Clear website background?')) return;
  document.getElementById('page-bg-preview').src = '';
  document.getElementById('page-bg-preview').style.display = 'none';
  await fetch(`${API}/api/admin/settings`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({page_bg:''})
  });
  alert('Cleared');
}

async function clearWingoBg(){
  if(!confirm('Clear Wingo background?')) return;
  document.getElementById('wingo-bg-preview').src = '';
  document.getElementById('wingo-bg-preview').style.display = 'none';
  await fetch(`${API}/api/admin/settings`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({wingo_bg:''})
  });
  alert('Cleared');
}

async function addSlider(){
  const data = document.getElementById('slider-img-data').value;
  const link = document.getElementById('slider-link').value;
  const title = document.getElementById('slider-title').value;
  const sub = document.getElementById('slider-sub').value;
  if(!data){alert('Choose image');return;}
  await fetch(`${API}/api/admin/add-slider`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({image:data,link,title,sub})
  });
  document.getElementById('slider-img-data').value = '';
  document.getElementById('slider-img-preview').style.display = 'none';
  document.getElementById('slider-link').value = '';
  document.getElementById('slider-title').value = '';
  document.getElementById('slider-sub').value = '';
  loadSliders();
}

async function loadSliders(){
  const r = await fetch(`${API}/api/admin/sliders`);
  const d = await r.json();
  let html = '';
  d.sliders.forEach((s,i)=>{
    html += `<div style="position:relative;background:rgba(20,10,35,0.8);padding:5px;border-radius:12px;border:1px solid rgba(157,78,221,0.3);">
      <img src="${s.image}" style="width:100%;border-radius:8px;height:100px;object-fit:cover;">
      <button onclick="deleteSlider(${i})" style="position:absolute;top:12px;right:12px;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;border:none;cursor:pointer;width:30px;height:30px;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.4);">X</button>
      ${s.title?`<div style="font-size:11px;color:#FFD700;margin-top:5px;text-align:center;">${s.title}</div>`:''}
    </div>`;
  });
  document.getElementById('slider-list').innerHTML = html;
}

async function deleteSlider(i){
  await fetch(`${API}/api/admin/delete-slider`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({index:i})
  });
  loadSliders();
}

async function createBonus(){
  const amt = document.getElementById('bonus-amt').value;
  const limit = document.getElementById('bonus-limit').value;
  if(!amt || !limit){alert('Fill all fields');return;}
  const r = await fetch(`${API}/api/admin/create-bonus`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({amount:parseFloat(amt),limit:parseInt(limit)})
  });
  const d = await r.json();
  if(d.success){
    document.getElementById('bonus-display').innerText = d.code;
    document.getElementById('bonus-result-box').style.display = 'block';
    loadBonusCodes();
  }
}

async function loadBonusCodes(){
  const r = await fetch(`${API}/api/admin/bonus-codes`);
  const d = await r.json();
  let html = '';
  d.codes.forEach(c=>{
    html += `<tr><td style="font-family:monospace;color:#FFD700;font-size:11px;">${c.code}</td><td>Ks ${fmt(c.amount)}</td><td>${c.used}/${c.limit}</td>
    <td><button onclick="deleteBonus('${c.code}')" style="color:red;background:none;border:none;cursor:pointer;">X</button></td></tr>`;
  });
  document.getElementById('bonus-list').innerHTML = html;
}

async function deleteBonus(code){
  await fetch(`${API}/api/admin/delete-bonus`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({code})
  });
  loadBonusCodes();
}

async function loadApiKey(){
  const r = await fetch(`${API}/api/admin/main-api-key`);
  const d = await r.json();
  if(d.success) document.getElementById('current-api-key').value = d.api_key;
  loadApiLogs();
}

function copyApiKey(){
  const k = document.getElementById('current-api-key').value;
  navigator.clipboard.writeText(k);
  alert('API Key copied');
}

async function changeApiKey(){
  const k = document.getElementById('new-api-key').value.trim();
  if(k.length < 8){alert('Minimum 8 characters');return;}
  const r = await fetch(`${API}/api/admin/main-api-key`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({api_key:k})
  });
  const d = await r.json();
  if(d.success){
    alert('API Key changed');
    document.getElementById('current-api-key').value = d.api_key;
    document.getElementById('new-api-key').value = '';
  } else alert(d.message || 'Failed');
}

async function loadApiLogs(){
  try{
    const r = await fetch(`${API}/api/admin/main-api-logs`);
    const d = await r.json();
    const body = document.getElementById('api-logs-body');
    if(!d.success || d.logs.length === 0){
      body.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:#666;">No logs</td></tr>';
      return;
    }
    let html = '';
    d.logs.forEach(l=>{
      const t = new Date(l.timestamp).toLocaleString();
      html += `<tr>
        <td style="font-size:10px;">${t}</td>
        <td style="font-family:monospace;color:#FFD700;font-size:11px;">${l.endpoint}</td>
        <td>${l.uid||'-'}</td>
        <td style="font-size:11px;">${l.ip||'-'}</td>
      </tr>`;
    });
    body.innerHTML = html;
  }catch(e){console.error(e);}
}

function applyAdminTheme(theme){
  const next = theme === 'light' ? 'light' : 'dark';
  document.body.setAttribute('data-theme', next);
  localStorage.setItem('gag_admin_theme', next);
  const b = document.getElementById('admin-theme-toggle');
  if(b) b.innerHTML = next === 'light' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
}
function toggleAdminTheme(){ applyAdminTheme(document.body.getAttribute('data-theme') === 'light' ? 'dark' : 'light'); }
applyAdminTheme(localStorage.getItem('gag_admin_theme') || 'dark');

loadDashboard();
</script>
</body>
</html>
'''

# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    return render_template_string(USER_HTML)

@app.route('/african-buffalo/')
def african_buffalo_index():
    return send_from_directory(AFRICAN_BUFFALO_DIR, 'index.html')

@app.route('/african-buffalo/<path:filename>')
def african_buffalo_asset(filename):
    return send_from_directory(AFRICAN_BUFFALO_DIR, filename)

def african_buffalo_user():
    payload = request.get_json(silent=True) or {}
    supplied = request.headers.get('X-Demo-User', '') or payload.get('uid', '')
    supplied = supplied or session.get('african_buffalo_uid', '')
    uid = ''.join(ch for ch in str(supplied).strip() if ch.isalnum() or ch in ('_', '-'))[:64]
    return get_user_by_uid(uid) if uid else None

def african_buffalo_room_id(data=None):
    data = data or {}
    raw = data.get('roomId') or request.headers.get('X-Buffalo-Room') or session.get('african_buffalo_room', 1)
    try:
        return max(1, min(4, int(raw)))
    except (TypeError, ValueError):
        return 1

def african_buffalo_default_rtp(room_id=1):
    try:
        settings = get_settings()
        return max(0.0, min(100.0, float(settings.get(f'african_buffalo_rtp_{room_id}', settings.get('african_buffalo_rtp', 96)))))
    except (TypeError, ValueError):
        return 96.0

@app.route('/api/african-buffalo/login', methods=['POST'])
def african_buffalo_login():
    user = african_buffalo_user()
    if not user or user.get('isBanned'):
        return jsonify({'resultid': 0, 'msg': 'Login required'}), 401
    room_id = african_buffalo_room_id(request.get_json(silent=True) or {})
    session['african_buffalo_uid'] = user['uid']
    session['african_buffalo_room'] = room_id
    session.setdefault('african_buffalo_free', {})
    return jsonify({'resultid': 1, 'Obj': {'nGamblingWinPool': 8888888,
        'score': african_buffalo_balance(user), 'userId': user['uid'],
        'roomId': room_id, 'rtp': african_buffalo_rtp_for_user(user, african_buffalo_default_rtp(room_id))}})

@app.route('/api/african-buffalo/balance')
def african_buffalo_balance_api():
    user = african_buffalo_user()
    if not user: return jsonify({'status': 'error', 'message': 'Login required'}), 401
    return jsonify({'status': 'ok', 'balance': african_buffalo_balance(user), 'userId': user['uid']})

@app.route('/api/african-buffalo/free-count')
def african_buffalo_free_count():
    room_id = african_buffalo_room_id()
    free = session.get('african_buffalo_free', {})
    if not isinstance(free, dict): free = {}
    return jsonify({'ResultCode': 1, 'freeCount': int(free.get(str(room_id), 0) or 0)})

@app.route('/api/african-buffalo/reset', methods=['POST'])
def african_buffalo_reset():
    user = african_buffalo_user()
    if not user: return jsonify({'status': 'error', 'message': 'Login required'}), 401
    # Reset only clears the current free-spin state; the shared site wallet is never recreated here.
    free = session.get('african_buffalo_free', {})
    if not isinstance(free, dict): free = {}
    free[str(african_buffalo_room_id())] = 0
    session['african_buffalo_free'] = free
    session.pop('african_buffalo_scatter_purchase_id', None)
    return jsonify({'status': 'ok', 'balance': african_buffalo_balance(user)})

@app.route('/api/african-buffalo/spin', methods=['POST'])
def african_buffalo_spin():
    user = african_buffalo_user()
    if not user or user.get('isBanned'):
        return jsonify({'ResultCode': 0, 'msg': 'Login required'}), 401
    data = request.get_json(silent=True) or {}
    client_spin_id = str(data.get('clientSpinId', '')).strip()[:120]
    cached_spin_id = str(session.get('african_buffalo_last_spin_id', '') or '')
    cached_spin_response = session.get('african_buffalo_last_spin_response')
    if client_spin_id and client_spin_id == cached_spin_id and isinstance(cached_spin_response, dict):
        return jsonify(cached_spin_response)
    bets = data.get('nBetList') or []
    try:
        # nBetList is a per-row/per-line stake list in the embedded client.
        # The authoritative wager is its sum, never just the first row.
        parsed_bets = [max(0, int(value)) for value in bets]
        bet = sum(parsed_bets) if parsed_bets else int(data.get('bet', 0) or 0)
    except (TypeError, ValueError):
        bet = 0
    if bet <= 0: bet = 80 * max(1, int(data.get('bet', 0) or 0) + 1)
    try:
        bet_multiplier = max(1, int(data.get('betMultiplier', data.get('nBetMultiple', 1)) or 1))
    except (TypeError, ValueError):
        bet_multiplier = 1
    before = african_buffalo_balance(user)
    room_id = african_buffalo_room_id(data)
    free_map = session.get('african_buffalo_free', {})
    if not isinstance(free_map, dict): free_map = {}
    free_remaining = int(free_map.get(str(room_id), 0) or 0)
    free_mode = free_remaining > 0
    if not free_mode and before < bet:
        return jsonify({'ResultCode': 0, 'msg': 'Insufficient balance', 'userscore': before})
    rtp = african_buffalo_rtp_for_user(user, african_buffalo_default_rtp(room_id))
    if free_mode:
        bet = int(session.get('african_buffalo_avg_bet', bet) or bet)
    result = african_buffalo_spin_result(bet, rtp, free_mode=free_mode, bet_multiplier=bet_multiplier)
    if not free_mode:
        african_buffalo_debit_playable(user, bet)
        record_turnover(user, bet, 'African Buffalo')
        user['totalBet'] = user.get('totalBet', 0) + bet
        session['african_buffalo_avg_bet'] = bet
    actual_win = max(0, int(result.get('win_amount', 0) or 0))
    # Credit exactly once. The client receives the same actual win amount used here;
    # display tiers must never be used as wallet amounts.
    if actual_win > 0:
        african_buffalo_credit_win(user, actual_win)
    after = african_buffalo_balance(user)
    update_user(user['uid'], user)
    free_count = max(0, free_remaining - 1) if free_mode else free_remaining
    free_count += result['free_award']
    free_map[str(room_id)] = free_count
    session['african_buffalo_free'] = free_map
    history = load_json(AFRICAN_BUFFALO_HISTORY_FILE, [])
    history.append({'game': 'African Buffalo', 'uid': user['uid'], 'bet': 0 if free_mode else bet,
        'win': actual_win, 'rtp': round((actual_win / bet * 100) if bet else 0, 2),
        'target_rtp': rtp, 'room_id': room_id, 'free_mode': free_mode,
        'bet_multiplier': bet_multiplier,
        'balance_before': before, 'balance_after': after,
        'scatter_count': result['scatter_count'], 'free_award': result['free_award'],
        'timestamp': datetime.now().isoformat()})
    save_json(AFRICAN_BUFFALO_HISTORY_FILE, history[-10000:])
    response_payload = {'ResultCode': 1, 'ResultData': {'userscore': after,
        'winscore': actual_win, 'actualWin': actual_win, 'freeCount': free_count,
        'viewarray': african_buffalo_view_result(result)}}
    if client_spin_id:
        session['african_buffalo_last_spin_id'] = client_spin_id
        session['african_buffalo_last_spin_response'] = response_payload
    return jsonify(response_payload)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    contact = str(data.get('contact', '')).strip()
    password = str(data.get('password', ''))
    ref_code = str(data.get('refCode', '')).strip()
    
    if not name or not contact or not password:
        return jsonify({'success': False, 'message': 'Fill all fields'})
    if get_user_by_contact(contact):
        return jsonify({'success': False, 'message': 'Phone already registered'})
    
    settings = get_settings()
    signup_bonus = settings.get('signup_bonus', 5000)
    referral_bonus = settings.get('referral_bonus', 2000)

    uid = generate_uid()
    users = load_json(USERS_FILE, [])
    users.append({
        'uid': uid, 'name': name, 'contact': contact, 'password': password,
        'refCodeUsed': ref_code or '',
        'wallet': {'deposit': 0, 'winning': 0, 'bonus': signup_bonus},
        'history': [], 'isBanned': False,
        'hasDeposited': False, 'totalDeposit': 0, 'totalBet': 0, 'lastDepositAmount': 0,
        'memberBonusEligible': True, 'memberBonusClaimed': False, 'memberBonusAvailable': 0,
        'createdAt': datetime.now().isoformat()
    })
    save_json(USERS_FILE, users)

    if ref_code:
        referrer = get_user_by_uid(ref_code)
        if referrer:
            referrer['wallet']['bonus'] = referrer['wallet'].get('bonus', 0) + referral_bonus
            update_user(ref_code, referrer)

    return jsonify({'success': True, 'uid': uid, 'bonus': signup_bonus})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    contact = str(data.get('contact', '')).strip()
    password = str(data.get('password', ''))
    
    if not contact or not password:
        return jsonify({'success': False, 'message': 'Fill all fields'})
    u = get_user_by_contact(contact)
    if not u:
        return jsonify({'success': False, 'message': 'Account not found. Please register.'})
    if str(u.get('password', '')) != password:
        return jsonify({'success': False, 'message': 'Wrong password'})
    if u.get('isBanned'):
        return jsonify({'success': False, 'message': 'Account banned'})
    return jsonify({'success': True, 'uid': u['uid']})

@app.route('/api/user/<uid>')
def api_user(uid):
    u = get_user_by_uid(uid)
    if u:
        return jsonify({'success': True, 'user': u})
    return jsonify({'success': False})

@app.route('/api/demo-games')
def api_demo_games():
    return jsonify({'success': True, 'games': get_demo_games()})

@app.route('/api/sliders-public')
def api_sliders_public():
    return jsonify({'success': True, 'sliders': load_json(SLIDERS_FILE, [])})

@app.route('/api/settings')
def api_settings():
    s = get_settings()
    response = jsonify({
        'success': True,
        'kpay_phone': s.get('kpay_phone', ''),
        'kpay_name': s.get('kpay_name', ''),
        'kpay_logo': s.get('kpay_logo', ''),
        'wave_phone': s.get('wave_phone', '09691835083'),
        'wave_name': s.get('wave_name', ''),
        'wave_logo': s.get('wave_logo', ''),
        'support_link': s.get('support_link', 'https://t.me/YourSupport'),
        'app_name': s.get('app_name', 'GAG2026'),
        'app_logo': s.get('app_logo', ''),
        'login_bg': s.get('login_bg', ''),
        'ingame_bg': s.get('ingame_bg', ''),
        'page_bg': s.get('page_bg', ''),
        'wingo_bg': s.get('wingo_bg', ''),
        'wingo_logo': s.get('wingo_logo', ''),
        'african_buffalo_logo': s.get('african_buffalo_logo', ''),
        'icon_pack': s.get('icon_pack', {}),
        'rules_text': s.get('rules_text', ''),
        'min_deposit': s.get('min_deposit', 1000),
        'min_withdraw': s.get('min_withdraw', 10000),
        'signup_bonus': s.get('signup_bonus', 5000),
        'referral_bonus': s.get('referral_bonus', 2000)
    })
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/api/deposit', methods=['POST'])
def api_deposit():
    data = request.get_json() or {}
    uid = data.get('uid')
    amount = int(data.get('amount', 0))
    utr = str(data.get('utr', '')).strip()
    method = (data.get('method') or 'kpay').lower()

    if not uid:
        return jsonify({'success': False, 'message': 'UID missing'})
    u = get_user_by_uid(uid)
    if not u:
        return jsonify({'success': False, 'message': 'User not found'})
    allowed, reason = can_open_wallet_action(u)
    if not allowed:
        return jsonify({'success': False, 'message': reason})
    if amount < 1000:
        return jsonify({'success': False, 'message': 'Minimum 1,000 Ks'})
    if not utr or len(utr) < 6:
        return jsonify({'success': False, 'message': 'Invalid Transaction ID'})

    existing = [d for d in load_json(DEPOSITS_FILE, []) if d.get('utr') == utr and d.get('uid') == uid]
    if existing:
        return jsonify({'success': False, 'message': 'Transaction ID already used'})

    deposits = load_json(DEPOSITS_FILE, [])
    deposits.append({
        'id': str(len(deposits) + 1),
        'uid': uid, 'amount': amount, 'utr': utr,
        'method': method, 'status': 'pending',
        'date': datetime.now().isoformat()
    })
    save_json(DEPOSITS_FILE, deposits)
    print(f"[DEPOSIT] UID={uid} | amount={amount} | method={method} | pending")
    return jsonify({'success': True, 'message': 'Submitted! Wait for admin approval.'})

@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    data = request.get_json(silent=True) or {}
    u = get_user_by_uid(data.get('uid'))
    if not u:
        return jsonify({'success': False, 'message': 'User not found'})
    if u.get('password') != data.get('password'):
        return jsonify({'success': False, 'message': 'Wrong password'})
    allowed, reason = can_open_wallet_action(u)
    if not allowed:
        return jsonify({'success': False, 'message': reason})
    try:
        amt = int(data.get('amount', 0))
    except (TypeError, ValueError):
        amt = 0
    settings = get_settings()
    min_withdraw = int(settings.get('min_withdraw', 10000) or 10000)
    if amt < min_withdraw:
        return jsonify({'success': False, 'message': f'Minimum {min_withdraw:,} Ks'})
    wallet = u.setdefault('wallet', {})
    playable = int(wallet.get('deposit', 0) or 0) + int(wallet.get('winning', 0) or 0)
    if playable < amt:
        return jsonify({'success': False, 'message': f'Insufficient playable balance. Available: {playable:,} Ks'})
    # Deduct from winning first, then the deposit wallet, matching betting and UI balance rules.
    from_winning = min(int(wallet.get('winning', 0) or 0), amt)
    wallet['winning'] = int(wallet.get('winning', 0) or 0) - from_winning
    remaining = amt - from_winning
    if remaining:
        wallet['deposit'] = int(wallet.get('deposit', 0) or 0) - remaining
    update_user(u['uid'], u)

    withdrawals = load_json(WITHDRAWALS_FILE, [])
    withdrawals.append({
        'id': str(len(withdrawals) + 1),
        'uid': u['uid'], 'amount': amt,
        'method': data.get('method', 'kpay'),
        'phone': data.get('phone'),
        'name': data.get('name'),
        'details': f"{data.get('method','kpay').upper()} - {data.get('phone')}",
        'status': 'pending',
        'date': datetime.now().isoformat()
    })
    save_json(WITHDRAWALS_FILE, withdrawals)
    return jsonify({'success': True})

@app.route('/api/history/<uid>')
def api_history(uid):
    deps = load_json(DEPOSITS_FILE, [])
    withs = load_json(WITHDRAWALS_FILE, [])
    history = []
    for d in deps:
        if d.get('uid') == uid:
            history.append({**d, 'type': 'Deposit'})
    for w in withs:
        if w.get('uid') == uid:
            history.append({**w, 'type': 'Withdraw'})
    history.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'success': True, 'history': history})

@app.route('/api/place-bet', methods=['POST'])
def api_place_bet():
    data = request.get_json()
    u = get_user_by_uid(data.get('uid'))
    if not u:
        return jsonify({'success': False, 'message': 'User not found'})

    wallet = u['wallet']
    playable = (wallet.get('deposit', 0) or 0) + (wallet.get('winning', 0) or 0)
    amt = data.get('amount')
    if playable < amt:
        return jsonify({'success': False, 'message': 'Insufficient balance'})

    rem = amt
    if wallet.get('winning', 0) >= rem:
        wallet['winning'] -= rem; rem = 0
    else:
        rem -= wallet.get('winning', 0); wallet['winning'] = 0
    if rem > 0:
        wallet['deposit'] = max(0, wallet.get('deposit', 0) - rem)

    record_turnover(u, amt, 'Wingo')
    u['totalBet'] = u.get('totalBet', 0) + amt
    update_user(u['uid'], u)

    bets = load_json(BETS_FILE, [])
    bets.append({
        'id': str(len(bets) + 1),
        'uid': u['uid'],
        'period': data.get('period'),
        'gameTimer': data.get('gameTimer'),
        'select': data.get('select'),
        'amount': amt,
        'status': 'pending',
        'timestamp': datetime.now().isoformat()
    })
    save_json(BETS_FILE, bets)
    return jsonify({'success': True})

@app.route('/api/check-bets', methods=['POST'])
def api_check_bets():
    data = request.get_json()
    uid = data.get('uid')
    dur = data.get('duration')
    period = data.get('period')
    res = data.get('result')
    number = res['number']
    is_red = number in [0, 2, 4, 6, 8]
    is_green = number in [1, 3, 5, 7, 9]
    is_violet = number in [0, 5]

    bets = load_json(BETS_FILE, [])
    total_win = 0
    had_bets = False
    updated = False
    for b in bets:
        if (b.get('uid') == uid and b.get('gameTimer') == dur
                and b.get('period') == period and b.get('status') == 'pending'):
            had_bets = True
            sel = b['select']
            win = False; payout = 0
            if sel == 'Green' and is_green:
                win = True; payout = b['amount'] * 1.5 if number == 5 else b['amount'] * 2
            elif sel == 'Red' and is_red:
                win = True; payout = b['amount'] * 1.5 if number == 0 else b['amount'] * 2
            elif sel == 'Violet' and is_violet:
                win = True; payout = b['amount'] * 4.5
            elif sel == 'Big' and res['size'] == 'Big':
                win = True; payout = b['amount'] * 2
            elif sel == 'Small' and res['size'] == 'Small':
                win = True; payout = b['amount'] * 2
            elif sel.isdigit() and int(sel) == number:
                win = True; payout = b['amount'] * 9
            b['status'] = 'win' if win else 'loss'
            b['payout'] = payout if win else 0
            updated = True
            if win: total_win += payout

    if updated: save_json(BETS_FILE, bets)
    if total_win > 0:
        u = get_user_by_uid(uid)
        if u:
            u['wallet']['winning'] = u['wallet'].get('winning', 0) + total_win
            update_user(uid, u)
    return jsonify({'success': True, 'total_win': total_win, 'had_bets': had_bets})

@app.route('/api/user-bets/<uid>')
def api_user_bets(uid):
    bets = [b for b in load_json(BETS_FILE, []) if b.get('uid') == uid]
    bets.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'bets': bets[:100]})

@app.route('/api/save-result', methods=['POST'])
def api_save_result():
    data = request.get_json()
    history = load_json(GAME_HISTORY_FILE, [])
    if not any(h.get('period') == data.get('period') and h.get('duration') == data.get('duration') for h in history):
        history.append(data)
        save_json(GAME_HISTORY_FILE, history[-5000:])
    return jsonify({'success': True})

@app.route('/api/game-history/<int:duration>')
def api_game_history(duration):
    history = [h for h in load_json(GAME_HISTORY_FILE, []) if h.get('duration') == duration]
    history.sort(key=lambda x: x.get('period', ''), reverse=True)
    return jsonify({'success': True, 'history': history[:200]})

@app.route('/api/redeem-bonus', methods=['POST'])
def api_redeem_bonus():
    data = request.get_json()
    uid = data.get('uid')
    code = data.get('code')
    u = get_user_by_uid(uid)
    if not u:
        return jsonify({'success': False, 'message': 'User not found'})
    
    has_deposited = u.get('hasDeposited', False) or ((u.get('wallet', {}).get('deposit', 0)) > 0)
    if not has_deposited:
        return jsonify({'success': False, 'message': 'Deposit first to unlock bonus'})
    
    codes = load_json(BONUS_CODES_FILE, [])
    for c in codes:
        if c.get('code') == code:
            if c.get('used', 0) >= c.get('limit', 0):
                return jsonify({'success': False, 'message': 'Code fully used'})
            if uid in c.get('claimed_by', []):
                return jsonify({'success': False, 'message': 'Already claimed'})
            amount = int(c.get('amount', 0) or 0)
            u['wallet']['winning'] = u['wallet'].get('winning', 0) + amount
            update_user(uid, u)
            c['used'] = c.get('used', 0) + 1
            c['claimed_by'] = c.get('claimed_by', []) + [uid]
            save_json(BONUS_CODES_FILE, codes)
            logs = load_json(BONUS_LOGS_FILE, [])
            logs.append({'uid': uid, 'code': code, 'amount': amount, 'credited_to': 'winning', 'timestamp': datetime.now().isoformat()})
            save_json(BONUS_LOGS_FILE, logs)
            return jsonify({'success': True, 'amount': amount, 'wallet': 'winning'})
    return jsonify({'success': False, 'message': 'Invalid code'})

@app.route('/api/claim-member-bonus', methods=['POST'])
def api_claim_member_bonus():
    data = request.get_json() or {}
    user = get_user_by_uid(data.get('uid'))
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    amount = int(user.get('memberBonusAvailable', 0) or 0)
    if user.get('memberBonusClaimed') or amount <= 0:
        return jsonify({'success': False, 'message': 'Member bonus is not available'})
    user.setdefault('wallet', {})['winning'] = int(user['wallet'].get('winning', 0) or 0) + amount
    user['memberBonusAvailable'] = 0
    user['memberBonusClaimed'] = True
    user['bonusWagered'] = 0
    user['bonusWagerRequired'] = amount * 12
    update_user(user['uid'], user)
    return jsonify({'success': True, 'amount': amount, 'required': amount * 12})

@app.route('/api/bonus-history/<uid>')
def api_bonus_history(uid):
    logs = [l for l in load_json(BONUS_LOGS_FILE, []) if l.get('uid') == uid]
    logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'history': logs[:20]})

@app.route('/api/notifications/<uid>')
def api_notifications(uid):
    notifs = [n for n in load_json(NOTIFICATIONS_FILE, [])
              if n.get('type') == 'global' or n.get('targetUid') == uid]
    notifs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'notifications': notifs[:20]})

# ============================================================
# MAIN API
# ============================================================
def check_api_key():
    return request.headers.get('X-API-Key', '') == get_main_api_key()

def api_response(success, data=None, message=None, status=200):
    res = {'success': success}
    if data is not None: res['data'] = data
    if message: res['message'] = message
    return jsonify(res), status

@app.route('/api/main/login', methods=['POST'])
def main_api_login():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/login', data.get('contact'), data, request.remote_addr)
    u = get_user_by_contact(data.get('contact'))
    if u and u.get('password') == data.get('password'):
        if u.get('isBanned'):
            return api_response(False, message='Banned', status=403)
        return api_response(True, data={'uid': u['uid'], 'user': u})
    return api_response(False, message='Invalid credentials', status=401)

@app.route('/api/main/user/<uid>', methods=['GET'])
def main_api_user(uid):
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    log_api_request(f'/api/main/user/{uid}', uid, {}, request.remote_addr)
    u = get_user_by_uid(uid)
    if u: return api_response(True, data={'user': u})
    return api_response(False, message='Not found', status=404)

@app.route('/api/main/balance', methods=['POST'])
def main_api_balance():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/balance', None, data, request.remote_addr)
    users = []
    for uid in data.get('uids', []):
        u = get_user_by_uid(uid)
        if u: users.append({'uid': u['uid'], 'name': u.get('name'), 'wallet': u.get('wallet', {})})
    return api_response(True, data={'users': users})

@app.route('/api/main/bet', methods=['POST'])
def main_api_bet():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/bet', data.get('uid'), data, request.remote_addr)
    return api_place_bet()

@app.route('/api/main/bet-multi', methods=['POST'])
def main_api_bet_multi():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/bet-multi', None, data, request.remote_addr)
    results = []
    for bet in data.get('bets', []):
        uid = bet.get('uid')
        u = get_user_by_uid(uid)
        if not u:
            results.append({'uid': uid, 'success': False}); continue
        wallet = u['wallet']
        playable = (wallet.get('deposit', 0) or 0) + (wallet.get('winning', 0) or 0)
        amt = bet.get('amount', 0)
        if playable < amt:
            results.append({'uid': uid, 'success': False}); continue
        rem = amt
        if wallet.get('winning', 0) >= rem: wallet['winning'] -= rem; rem = 0
        else: rem -= wallet.get('winning', 0); wallet['winning'] = 0
        if rem > 0: wallet['deposit'] = max(0, wallet.get('deposit', 0) - rem)
        record_turnover(u, amt, bet.get('game', 'Wingo'))
        u['totalBet'] = u.get('totalBet', 0) + amt
        update_user(uid, u)
        all_bets = load_json(BETS_FILE, [])
        all_bets.append({
            'id': str(len(all_bets) + 1), 'uid': uid,
            'period': bet.get('period'), 'gameTimer': bet.get('gameTimer'),
            'select': bet.get('select'), 'amount': amt,
            'status': 'pending', 'timestamp': datetime.now().isoformat()
        })
        save_json(BETS_FILE, all_bets)
        results.append({'uid': uid, 'success': True})
    return api_response(True, data={'results': results})

@app.route('/api/main/deposit', methods=['POST'])
def main_api_deposit():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/deposit', data.get('uid'), data, request.remote_addr)
    return api_deposit()

@app.route('/api/main/withdraw', methods=['POST'])
def main_api_withdraw():
    if not check_api_key(): return api_response(False, message='Invalid API Key', status=401)
    data = request.get_json() or {}
    log_api_request('/api/main/withdraw', data.get('uid'), data, request.remote_addr)
    return api_withdraw()

# ============================================================
# ADMIN - MAIN API
# ============================================================
@app.route('/api/admin/main-api-key', methods=['GET'])
def admin_get_main_api_key():
    if not require_admin(): return jsonify({'success': False}), 401
    return jsonify({'success': True, 'api_key': get_main_api_key()})

@app.route('/api/admin/main-api-key', methods=['POST'])
def admin_set_main_api_key():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json() or {}
    new_key = data.get('api_key', '').strip()
    if len(new_key) < 8:
        return jsonify({'success': False, 'message': 'Minimum 8 characters'})
    s = get_settings()
    s['main_api_key'] = new_key
    save_json(SETTINGS_FILE, s)
    return jsonify({'success': True, 'api_key': new_key})

@app.route('/api/admin/main-api-logs', methods=['GET'])
def admin_main_api_logs():
    if not require_admin(): return jsonify({'success': False}), 401
    logs = load_json(API_LOG_FILE, [])
    return jsonify({'success': True, 'logs': list(reversed(logs[-100:]))})

# ============================================================
# ADMIN ROUTES
# ============================================================
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    creds = get_admin_creds()
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u == creds.get('username') and p == creds.get('password'):
            session['is_admin'] = True
            return redirect('/admin')
        return render_template_string(ADMIN_LOGIN_HTML, error="Invalid credentials")
    if not session.get('is_admin'):
        return render_template_string(ADMIN_LOGIN_HTML, error="")
    return render_template_string(ADMIN_HTML)

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect('/admin')

def require_admin():
    return session.get('is_admin')

@app.route('/api/admin/current-creds')
def admin_current_creds():
    if not require_admin(): return jsonify({'success': False}), 401
    creds = get_admin_creds()
    return jsonify({'success': True, 'username': creds.get('username')})

@app.route('/api/admin/change-creds', methods=['POST'])
def admin_change_creds():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    creds = get_admin_creds()
    if data.get('currentPassword') != creds.get('password'):
        return jsonify({'success': False, 'message': 'Current password wrong'})
    if data.get('newUsername'):
        creds['username'] = data.get('newUsername')
    if data.get('newPassword'):
        creds['password'] = data.get('newPassword')
    save_json(ADMIN_CRED_FILE, creds)
    return jsonify({'success': True})

@app.route('/api/admin/dashboard')
def admin_dashboard():
    if not require_admin(): return jsonify({'success': False}), 401
    users = load_json(USERS_FILE, [])
    deps = load_json(DEPOSITS_FILE, [])
    withs = load_json(WITHDRAWALS_FILE, [])
    total_dep = sum(d['amount'] for d in deps if d.get('status') == 'success')
    total_with = sum(w['amount'] for w in withs if w.get('status') == 'success')
    pending = len([d for d in deps if d.get('status') == 'pending']) + len([w for w in withs if w.get('status') == 'pending'])
    return jsonify({'total_users': len(users), 'total_deposits': total_dep,
                    'total_withdrawals': total_with, 'pending': pending})

@app.route('/api/admin/deposits')
def admin_deposits():
    if not require_admin(): return jsonify({'success': False}), 401
    deps = [d for d in load_json(DEPOSITS_FILE, []) if d.get('status') == 'pending']
    deps.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'deposits': deps})

@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    if not require_admin(): return jsonify({'success': False}), 401
    ws = [w for w in load_json(WITHDRAWALS_FILE, []) if w.get('status') == 'pending']
    ws.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'withdrawals': ws})

@app.route('/api/admin/process-txn', methods=['POST'])
def admin_process_txn():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    txn_id = str(data.get('id'))
    uid = data.get('uid')
    amt = data.get('amount')
    action = data.get('action')
    txn_type = data.get('type')

    if txn_type == 'dep':
        deps = load_json(DEPOSITS_FILE, [])
        for d in deps:
            if str(d.get('id')) == txn_id:
                d['status'] = 'success' if action == 'approve' else 'rejected'
                if action == 'approve':
                    d['approved_at'] = datetime.now().isoformat()
        save_json(DEPOSITS_FILE, deps)
        if action == 'approve':
            u = get_user_by_uid(uid)
            if u:
                balance_before = wallet_total(u)
                u['wallet']['deposit'] = u['wallet'].get('deposit', 0) + amt
                u['hasDeposited'] = True
                u['totalDeposit'] = u.get('totalDeposit', 0) + amt
                u['lastDepositAmount'] = amt
                u['depositWagered'] = 0
                u['depositWagerRequired'] = int(amt)
                d['balance_before'] = balance_before
                if int(amt) >= 10000 and u.get('memberBonusEligible', False) and not u.get('memberBonusClaimed'):
                    u['memberBonusAvailable'] = 10000
                promote_bonus_to_real(u)
                save_json(DEPOSITS_FILE, deps)
                update_user(uid, u)
    else:
        ws = load_json(WITHDRAWALS_FILE, [])
        for w in ws:
            if str(w.get('id')) == txn_id:
                w['status'] = 'success' if action == 'approve' else 'rejected'
        save_json(WITHDRAWALS_FILE, ws)
        if action == 'reject':
            u = get_user_by_uid(uid)
            if u:
                u['wallet']['winning'] = u['wallet'].get('winning', 0) + amt
                update_user(uid, u)
    return jsonify({'success': True})

@app.route('/api/admin/users')
def admin_users():
    if not require_admin(): return jsonify({'success': False}), 401
    return jsonify({'users': load_json(USERS_FILE, [])})

@app.route('/api/admin/african-buffalo/settings', methods=['GET', 'POST'])
def admin_african_buffalo_settings():
    if not require_admin(): return jsonify({'success': False}), 401
    settings = get_settings()
    if request.method == 'POST':
        data = request.get_json() or {}
        try:
            settings['african_buffalo_rtp'] = max(0.0, min(100.0, float(data.get('rtp', 96))))
            for room_id in range(1, 5):
                key = f'room_{room_id}'
                if key in data:
                    settings[f'african_buffalo_rtp_{room_id}'] = max(0.0, min(100.0, float(data[key])))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid RTP'}), 400
        save_json(SETTINGS_FILE, settings)
    return jsonify({'success': True, 'rtp': float(settings.get('african_buffalo_rtp', 96)),
                    'rooms': {str(i): float(settings.get(f'african_buffalo_rtp_{i}', settings.get('african_buffalo_rtp', 96))) for i in range(1, 5)}})

@app.route('/api/admin/african-buffalo/user-rtp', methods=['POST'])
def admin_african_buffalo_user_rtp():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json() or {}
    user = get_user_by_uid(str(data.get('uid', '')))
    if not user: return jsonify({'success': False, 'message': 'User not found'}), 404
    try:
        rtp = max(0.0, min(100.0, float(data.get('rtp', 96))))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid RTP'}), 400
    user['africanBuffaloRtp'] = rtp
    update_user(user['uid'], user)
    return jsonify({'success': True, 'uid': user['uid'], 'rtp': rtp})

@app.route('/api/admin/african-buffalo/history/<uid>')
def admin_african_buffalo_history(uid):
    if not require_admin(): return jsonify({'success': False}), 401
    history = [h for h in load_json(AFRICAN_BUFFALO_HISTORY_FILE, []) if h.get('uid') == uid]
    history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'history': history[:500]})

# ============ DOWNLOAD JSON EXPORT ============
@app.route('/api/admin/user-export/<uid>')
def admin_user_export(uid):
    if not require_admin(): return jsonify({'success': False}), 401
    u = get_user_by_uid(uid)
    if not u:
        return jsonify({'success': False, 'message': 'User not found'})
    
    deps = load_json(DEPOSITS_FILE, [])
    withs = load_json(WITHDRAWALS_FILE, [])
    bets = load_json(BETS_FILE, [])
    
    userDeps = [d for d in deps if d.get('uid') == uid]
    userWiths = [w for w in withs if w.get('uid') == uid]
    userBets = [b for b in bets if b.get('uid') == uid]
    buffalo_history = [h for h in load_json(AFRICAN_BUFFALO_HISTORY_FILE, []) if h.get('uid') == uid]
    
    totalDeposit = sum(d['amount'] for d in userDeps if d.get('status') == 'success')
    totalWithdraw = sum(w['amount'] for w in userWiths if w.get('status') == 'success')
    totalBetAmount = sum(b.get('amount', 0) for b in userBets)
    totalWinAmount = sum(b.get('payout', 0) for b in userBets if b.get('status') == 'win')
    
    export_data = {
        'exported_at': datetime.now().isoformat(),
        'game': 'GAG2026',
        'user_info': {
            'uid': u.get('uid'),
            'name': u.get('name'),
            'contact': u.get('contact'),
            'password': u.get('password'),
            'wallet': u.get('wallet', {}),
            'hasDeposited': u.get('hasDeposited', False),
            'isBanned': u.get('isBanned', False),
            'totalDeposit': u.get('totalDeposit', 0),
            'totalBet': u.get('totalBet', 0),
            'createdAt': u.get('createdAt')
        },
        'summary': {
            'total_deposits_count': len(userDeps),
            'total_deposits_amount': totalDeposit,
            'total_withdrawals_count': len(userWiths),
            'total_withdrawals_amount': totalWithdraw,
            'total_bets_count': len(userBets),
            'total_bets_amount': totalBetAmount,
            'total_wins_amount': totalWinAmount
        },
        'deposits': sorted(userDeps, key=lambda x: x.get('date', ''), reverse=True),
        'withdrawals': sorted(userWiths, key=lambda x: x.get('date', ''), reverse=True),
        'bets': sorted(userBets, key=lambda x: x.get('timestamp', ''), reverse=True)[:500],
        'african_buffalo_history': sorted(buffalo_history, key=lambda x: x.get('timestamp', ''), reverse=True)[:500]
    }
    return jsonify({'success': True, 'data': export_data})

@app.route('/api/admin/export-all')
def admin_export_all():
    if not require_admin(): return jsonify({'success': False}), 401
    users = load_json(USERS_FILE, [])
    deps = load_json(DEPOSITS_FILE, [])
    withs = load_json(WITHDRAWALS_FILE, [])
    bets = load_json(BETS_FILE, [])
    buffalo_history_all = load_json(AFRICAN_BUFFALO_HISTORY_FILE, [])
    
    users_export = []
    for u in users:
        uid = u.get('uid')
        userDeps = [d for d in deps if d.get('uid') == uid]
        userWiths = [w for w in withs if w.get('uid') == uid]
        userBets = [b for b in bets if b.get('uid') == uid]
        userBuffaloHistory = [h for h in buffalo_history_all if h.get('uid') == uid]
        totalDeposit = sum(d['amount'] for d in userDeps if d.get('status') == 'success')
        totalWithdraw = sum(w['amount'] for w in userWiths if w.get('status') == 'success')
        totalBetAmount = sum(b.get('amount', 0) for b in userBets)
        totalWinAmount = sum(b.get('payout', 0) for b in userBets if b.get('status') == 'win')
        
        users_export.append({
            'user_info': {
                'uid': u.get('uid'), 'name': u.get('name'),
                'contact': u.get('contact'), 'password': u.get('password'),
                'wallet': u.get('wallet', {}),
                'hasDeposited': u.get('hasDeposited', False),
                'isBanned': u.get('isBanned', False),
                'createdAt': u.get('createdAt')
            },
            'summary': {
                'deposits_count': len(userDeps),
                'deposits_amount': totalDeposit,
                'withdrawals_count': len(userWiths),
                'withdrawals_amount': totalWithdraw,
                'bets_count': len(userBets),
                'bets_amount': totalBetAmount,
                'wins_amount': totalWinAmount
            },
            'deposits': sorted(userDeps, key=lambda x: x.get('date', ''), reverse=True),
            'withdrawals': sorted(userWiths, key=lambda x: x.get('date', ''), reverse=True),
            'bets': sorted(userBets, key=lambda x: x.get('timestamp', ''), reverse=True)[:500],
            'african_buffalo_history': sorted(userBuffaloHistory, key=lambda x: x.get('timestamp', ''), reverse=True)[:500]
        })
    
    grand_total_dep = sum(d['amount'] for d in deps if d.get('status') == 'success')
    grand_total_with = sum(w['amount'] for w in withs if w.get('status') == 'success')
    
    export_data = {
        'exported_at': datetime.now().isoformat(),
        'game': 'GAG2026',
        'total_users': len(users),
        'grand_summary': {
            'total_deposits_count': len(deps),
            'total_deposits_amount': grand_total_dep,
            'total_withdrawals_count': len(withs),
            'total_withdrawals_amount': grand_total_with,
            'total_bets_count': len(bets)
        },
        'users': users_export
    }
    return jsonify({'success': True, 'data': export_data})

@app.route('/api/admin/user-balance', methods=['POST'])
def admin_user_balance():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    u = get_user_by_uid(data.get('uid'))
    if not u: return jsonify({'success': False})
    wt = data.get('wallet')
    amt = data.get('amount')
    if data.get('action') == 'add':
        u['wallet'][wt] = u['wallet'].get(wt, 0) + amt
    else:
        u['wallet'][wt] = max(0, u['wallet'].get(wt, 0) - amt)
    update_user(u['uid'], u)
    return jsonify({'success': True})

@app.route('/api/admin/toggle-block', methods=['POST'])
def admin_toggle_block():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    u = get_user_by_uid(data.get('uid'))
    if u:
        u['isBanned'] = not u.get('isBanned', False)
        update_user(u['uid'], u)
    return jsonify({'success': True})

@app.route('/api/admin/notification', methods=['POST'])
def admin_notification():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    notifs = load_json(NOTIFICATIONS_FILE, [])
    notifs.append({
        'type': data.get('type'),
        'targetUid': data.get('uid') if data.get('type') == 'personal' else 'all',
        'title': data.get('title'),
        'message': data.get('message'),
        'timestamp': datetime.now().isoformat()
    })
    save_json(NOTIFICATIONS_FILE, notifs)
    return jsonify({'success': True})

@app.route('/api/admin/settings', methods=['POST'])
def admin_settings():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    s = get_settings()
    for k, v in data.items():
        if v is not None:
            s[k] = v
    save_json(SETTINGS_FILE, s)
    return jsonify({'success': True})

@app.route('/api/admin/remove-background', methods=['POST'])
def admin_remove_background():
    if not require_admin(): return jsonify({'success': False, 'message': 'Admin login required'}), 401
    data = request.get_json(silent=True) or {}
    try:
        result = remove_uniform_background(data.get('image'))
        return jsonify({'success': True, 'image': result})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

@app.route('/api/admin/create-bonus', methods=['POST'])
def admin_create_bonus():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))
    codes = load_json(BONUS_CODES_FILE, [])
    codes.append({'code': code, 'amount': data.get('amount'),
                  'limit': data.get('limit'), 'used': 0, 'claimed_by': []})
    save_json(BONUS_CODES_FILE, codes)
    return jsonify({'success': True, 'code': code})

@app.route('/api/admin/bonus-codes')
def admin_bonus_codes():
    if not require_admin(): return jsonify({'success': False}), 401
    return jsonify({'codes': load_json(BONUS_CODES_FILE, [])})

@app.route('/api/admin/delete-bonus', methods=['POST'])
def admin_delete_bonus():
    if not require_admin(): return jsonify({'success': False}), 401
    code = request.get_json().get('code')
    codes = [c for c in load_json(BONUS_CODES_FILE, []) if c.get('code') != code]
    save_json(BONUS_CODES_FILE, codes)
    return jsonify({'success': True})

@app.route('/api/admin/sliders')
def admin_sliders():
    if not require_admin(): return jsonify({'success': False}), 401
    return jsonify({'sliders': load_json(SLIDERS_FILE, [])})

@app.route('/api/admin/add-slider', methods=['POST'])
def admin_add_slider():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    sliders = load_json(SLIDERS_FILE, [])
    sliders.append({
        'image': data.get('image'),
        'link': data.get('link', ''),
        'title': data.get('title', ''),
        'sub': data.get('sub', '')
    })
    save_json(SLIDERS_FILE, sliders)
    return jsonify({'success': True})

@app.route('/api/admin/delete-slider', methods=['POST'])
def admin_delete_slider():
    if not require_admin(): return jsonify({'success': False}), 401
    idx = request.get_json().get('index')
    sliders = load_json(SLIDERS_FILE, [])
    if 0 <= idx < len(sliders):
        sliders.pop(idx)
        save_json(SLIDERS_FILE, sliders)
    return jsonify({'success': True})

@app.route('/api/admin/force-result', methods=['POST'])
def admin_force_result():
    if not require_admin(): return jsonify({'success': False}), 401
    data = request.get_json()
    forced = load_json(FORCED_RESULTS_FILE, [])
    forced.append({'duration': data.get('duration'), 'number': data.get('number'), 'used': False})
    save_json(FORCED_RESULTS_FILE, forced)
    return jsonify({'success': True})

# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("  GAG2026 - gag game site")
    print("=" * 60)
    print(f"  User App     : http://localhost:5000")
    print(f"  Admin Panel  : http://localhost:5000/admin")
    print(f"  Admin User   : admin")
    print(f"  Admin Pass   : jalwa123")
    print(f"  Games Loaded : {sum(len(v) for v in DEFAULT_GAMES.values()) if DEFAULT_GAMES else 0}")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
