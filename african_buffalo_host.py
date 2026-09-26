from __future__ import annotations

import math
import random

ROWS, COLS = 4, 5
WILD, SCATTER = 13, 12
PAYTABLE = {
    11: {2: 10, 3: 50, 4: 100, 5: 250},
    1: {3: 50, 4: 100, 5: 150},
    2: {3: 50, 4: 100, 5: 150},
    3: {3: 20, 4: 80, 5: 120},
    4: {3: 20, 4: 80, 5: 120},
    5: {3: 10, 4: 50, 5: 80},
    6: {3: 5, 4: 20, 5: 60},
    7: {3: 5, 4: 20, 5: 60},
    8: {3: 5, 4: 20, 5: 60},
    9: {3: 5, 4: 10, 5: 60},
    10: {3: 5, 4: 10, 5: 60},
}
SYMBOLS = list(PAYTABLE)
WEIGHTS = [12, 8, 8, 9, 9, 12, 13, 13, 13, 13, 13]


def pick_symbol():
    n = random.randrange(sum(WEIGHTS))
    for symbol, weight in zip(SYMBOLS, WEIGHTS):
        if n < weight:
            return symbol
        n -= weight
    return SYMBOLS[-1]


def random_grid(free_mode=False):
    grid = [[pick_symbol() for _ in range(ROWS)] for _ in range(COLS)]
    for col in (1, 2, 3):
        if random.randrange(100) < 7:
            grid[col][random.randrange(ROWS)] = WILD
    # Three or more scatters award free games; keep the base-game trigger rare.
    if random.randrange(10000) < (80 if free_mode else 50):
        count = (2 + random.randrange(4)) if free_mode else (3 + random.randrange(3))
        positions = [(c, r) for c in range(COLS) for r in range(ROWS)]
        random.shuffle(positions)
        for c, r in positions[:count]:
            grid[c][r] = SCATTER
    return grid


def add_random_win(grid):
    symbol = random.choice(SYMBOLS)
    length = 3 + random.randrange(3)
    row = random.randrange(ROWS)
    grid[0][row] = symbol
    for col in range(1, length):
        grid[col][random.randrange(ROWS)] = WILD if col in (1, 2, 3) and random.randrange(100) < 30 else symbol


def evaluate(grid):
    wins = []
    for symbol, pays in PAYTABLE.items():
        first = [r for r in range(ROWS) if grid[0][r] == symbol]
        if not first:
            continue
        positions = [first]
        length = 1
        for col in range(1, COLS):
            current = [r for r in range(ROWS) if grid[col][r] in (symbol, WILD)]
            if not current:
                break
            positions.append(current)
            length += 1
        if length < 3 or not pays.get(length):
            continue
        # The supplied paytable is a bet multiplier table. It is not an
        # all-ways table, so multiplying by every matching row overpays badly.
        ways = 1
        wins.append({'symbol': symbol, 'reels': length, 'ways': ways, 'multiplier': pays[length],
                     'positions': [(c, r) for c in range(length) for r in positions[c]],
                     'amount': pays[length]})
    return wins


def calculate_payout(bet, wins, free_multiplier=1, bet_multiplier=1):
    """Calculate one authoritative cash win from the supplied paytable.

    PAYTABLE values are cash amounts for the base bet of 80 Ks. A larger wager
    scales by bet / 80: 4,000 Ks is 50 base units, so a 10-Ks paytable result
    becomes 500 Ks. An explicit Bet Multiplier and free-spin multiplier apply
    after that base-bet scaling.
    """
    base_units = max(0.0, float(bet or 0) / 80.0)
    free_x = max(1, int(free_multiplier or 1))
    bet_x = max(1, int(bet_multiplier or 1))
    table_total = sum(max(0, int(item.get('multiplier', 0) or 0)) for item in (wins or []))
    return int(round(table_total * base_units * bet_x * free_x))


def spin_result(bet, rtp, free_mode=False, bet_multiplier=1):
    target = max(0.0, min(100.0, float(rtp)))
    # RTP extremes are deterministic at the authoritative server-result layer.
    if target <= 0:
        grid = [[pick_symbol() for _ in range(ROWS)] for _ in range(COLS)]
        wins = []
    else:
        grid = random_grid(free_mode=free_mode)
        # Calibrate the gate against this paytable, not against an arbitrary
        # win percentage. A normal candidate averages about 19% return while
        # a forced candidate averages about 119%; mixing them makes the
        # configured RTP observable over a large sample and avoids the old
        # 90% setting behaving like a ~20% game.
        forced_probability = max(0.0, min(1.0, (target - 19.0) / 100.0))
        if random.random() < forced_probability:
            add_random_win(grid)
        wins = evaluate(grid)
    base = sum(w['amount'] for w in wins)
    free_multiplier = 1
    if free_mode:
        wilds_on_bonus_reels = sum(1 for col in (1, 2, 3) for symbol in grid[col] if symbol == WILD)
        if wilds_on_bonus_reels:
            # The source paytable says x2/x3 per bonus-reel wild. Use the
            # strongest wild on a spin, avoiding accidental runaway payouts.
            free_multiplier = max(random.choice((2, 3)) for _ in range(wilds_on_bonus_reels))
    # Keep payout, Mega Win board value, history value, and wallet credit on
    # the same source of truth. No display tier may inflate this number.
    win = calculate_payout(bet, wins, free_multiplier, bet_multiplier)
    scatter = sum(1 for col in grid for symbol in col if symbol == SCATTER)
    free_award = ({2: 5, 3: 8, 4: 15, 5: 20} if free_mode else {3: 8, 4: 15, 5: 20}).get(scatter, 0)
    cards = []
    flags = [False] * 20
    details = []
    for row in range(ROWS - 1, -1, -1):
        for col in range(COLS):
            cards.append(grid[col][row])
    def display_index(col, row):
        return col + (ROWS - 1 - row) * COLS
    for item in wins:
        indexes = []
        for col, row in item['positions']:
            index = display_index(col, row)
            flags[index] = True
            indexes.append(index)
        details.append(indexes)
    return {
        'grid': grid, 'cards': cards, 'wins': wins, 'flags': flags, 'details': details,
        'scatter_count': scatter, 'free_award': free_award, 'free_multiplier': free_multiplier,
        'win_amount': win,
    }


def view_result(result):
    return {
        'nHandCards': result['cards'], 'nWinCards': result['flags'],
        'nWinLinesDetail': result['details'], 'fMultiple': result['free_multiplier'],
        'getFreeTime': {'bFlag': result['free_award'] > 0, 'nFreeTime': result['free_award']},
        'freeAnim': [0, 1, 2, 3, 4],
    }


def rtp_for_user(user, default=96):
    try:
        return max(0.0, min(100.0, float(user.get('africanBuffaloRtp', default))))
    except (TypeError, ValueError):
        return float(default)


def playable_balance(user):
    wallet = user.get('wallet', {})
    return int(wallet.get('deposit', 0) or 0) + int(wallet.get('winning', 0) or 0)


def debit_playable(user, amount):
    wallet = user.setdefault('wallet', {})
    remaining = int(amount)
    winning = int(wallet.get('winning', 0) or 0)
    used_winning = min(winning, remaining)
    wallet['winning'] = winning - used_winning
    remaining -= used_winning
    if remaining:
        wallet['deposit'] = max(0, int(wallet.get('deposit', 0) or 0) - remaining)


def credit_win(user, amount):
    wallet = user.setdefault('wallet', {})
    wallet['winning'] = int(wallet.get('winning', 0) or 0) + int(amount)


def balance(user):
    return playable_balance(user)
