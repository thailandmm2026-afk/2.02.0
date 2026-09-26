from pathlib import Path
from african_buffalo_host import calculate_payout

assert calculate_payout(80, [{'multiplier': 10}]) == 10
assert calculate_payout(4000, [{'multiplier': 10}]) == 500
assert calculate_payout(160, [{'multiplier': 50}]) == 100
assert calculate_payout(4000, [{'multiplier': 10}], free_multiplier=2) == 1000
slot = Path('slotapp.py').read_text()
assert 'const minWithdraw = Number(globalSettings && globalSettings.min_withdraw) || 10000;' in slot
assert "min_withdraw = int(settings.get('min_withdraw', 10000) or 10000)" in slot
assert 'object-fit:contain' in slot
print('latest fixes regression checks passed')
