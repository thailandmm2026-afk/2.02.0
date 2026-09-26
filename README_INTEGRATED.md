# GAG2026 + African Buffalo

This package embeds the African Buffalo game into the existing GAG2026 website. The home page now shows African Buffalo's four real-game rooms first, followed by Wingo. All other catalogue games are isolated underneath the heading **Demo Game များအပြင်းအပြေဆော့ရန်** and visibly marked **DEMO GAME**.

## Run

```bash
python3 -m pip install flask requests
python3 slotapp.py
```

Open `http://127.0.0.1:5000/`. The admin panel is at `http://127.0.0.1:5000/admin` with the default credentials `admin / jalwa123` unless changed in the panel.

## Shared wallet

African Buffalo uses the logged-in website user's existing `deposit + winning` balance. The bridge passes the website UID and selected room to the host routes, so the amount shown when entering the game is the current website amount. Each spin debits and credits the same user wallet, and closing the game refreshes the main website balance immediately.

## Admin controls

The admin panel's **Game Control** section contains a global African Buffalo RTP setting, four room-specific real RTP settings, and a Buffalo loading-logo upload. The **Users + Download** section lets an administrator set an individual user's African Buffalo RTP, view the latest history, download a dedicated `AfricanBuffalo_<uid>_<date>.json` history file, or download the broader user export. RTP values are limited to `0–100`; they are statistical targets and not guarantees for an individual spin.

The Buffalo paytable follows the supplied paytable image: wins use the listed bet multipliers once per symbol sequence rather than multiplying by every matching row. Base-game scatters are rare and award 8, 15, or 20 free games for 3, 4, or 5 scatters; free-game scatters award the additional 5, 8, 15, or 20 games described in the image. Signup and gift-code bonuses move into the playable winning wallet once the deposit unlock is satisfied. Withdrawals validate the same combined playable balance shown in the UI and deduct winning funds before deposit funds.

The African Buffalo bundle is game-only and does not ship its previous standalone admin panel, room-link API, or API-key controls. Its namespaced host routes exist only to synchronize the embedded demo game with the website wallet.
