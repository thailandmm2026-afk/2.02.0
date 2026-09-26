# htdocs-inspired Home rebuild

This build recreates the visual direction of the supplied htdocs Cocos lobby as an editable HTML/CSS home page: compact top bar, banner area, game sections, responsive game-card grid, persistent bottom navigation, side menu, and restrained splash loading bar. The player website is now locked to a clean white theme; the player theme switch has been removed.

The htdocs bundle itself is not used as the Buffalo game. The previously integrated web African Buffalo bundle remains active, including shared wallet synchronization, four-room RTP control, per-user RTP control, corrected payout handling, duplicate-spin protection, and history.

## Buffalo payout source of truth

The supplied paytable values are cash amounts for a **base bet of 80 Ks**. The payout scales by `actual bet / 80`: for example, a 10-Ks paytable result pays 10 Ks at an 80-Ks bet and 500 Ks at a 4,000-Ks bet. Matching cells are not multiplied again as hidden ways. An explicit Bet Multiplier and the free-spin Wild x2/x3 multiplier are applied separately. The same `actual_win` integer is used for wallet credit, history, `winscore`, `actualWin`, and the Mega Win animation, so a display tier cannot inflate the balance.

The Buffalo loading screen uses a bar-only default. If an administrator sets a loading image, it is rendered as a full-screen, landscape-oriented diagonal composition using a fixed rotation and cover fit rather than appearing as a stretched upright card. Game-card source images use contain-fit so the full artwork remains visible. The configured application logo is shown in the player top bar. Configured website and Wingo backgrounds remain visible behind their content.

## Games

The game area contains the previously integrated Wingo game, African Buffalo rooms, and the existing demo-game catalog from `gag_games.py`. No Golden Century or other additional htdocs game is included.

## Connected flows

The existing website handlers and backend routes remain connected to the redesigned lobby: registration/login, wallet balance display, deposit requests, withdrawal requests, gift-code bonuses, game history, notification center, Wingo play, Buffalo play, demo-game launch, and the admin panel. The default and enforced minimum withdrawal amount is 10,000 Ks; the admin payment settings can raise it further.

The admin panel remains the existing editable web admin, because the supplied htdocs archive contains a compiled Cocos canvas and does not include website-level deposit, withdrawal, bonus, or admin HTML. Admin controls include transaction approval, user balances, exports/history, Buffalo global/room/user RTP, Buffalo loading logo/background, bonus codes, sliders, notifications, API settings, and admin credentials.

## Run

```bash
python3 -m pip install flask requests
python3 slotapp.py
```

Open `http://127.0.0.1:5000/`; the admin panel is at `http://127.0.0.1:5000/admin`.

Default admin credentials: `admin / jalwa123`.

## Demo wallet note

Deposit and withdrawal are demo request/approval flows. No live payment provider is connected by this rebuild.

## Reset

Stop the server and remove runtime data for a clean demo state:

```bash
rm -rf data
```
