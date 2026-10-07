"""Settings for the paper desks. Edit, commit, and the next run picks them up.

Changing the grid range or capital after the first run only affects new
activity; delete the state file (the ``floor-data`` branch) to start over.
"""

# Paper capital per desk, USD.
START_CAPITAL = {"roc": 5000.0, "grid": 3000.0, "alpha": 2000.0}

# --- Desk 1: Return on Cash -------------------------------------------------
# Yahoo symbol for the 13-week T-bill yield (percent).
RATE_SYMBOL = "^IRX"

# --- Desk 2: Beta / Oil Grid ------------------------------------------------
GRID_SYMBOL = "CL=F"           # WTI front-month futures (continuous)
GRID_LABEL = "WTI"
GRID_STEP = 0.50               # dollars between grid levels
GRID_LEVELS_EACH_SIDE = 12     # levels above and below the starting price
GRID_BARRELS_PER_LEVEL = 10    # 0.01 lot of a 1,000-barrel oil CFD
# Fix the range yourself (e.g. 84.0 / 96.0); None centres it on the first price.
GRID_LO = None
GRID_HI = None
# A jump bigger than this between two bars is a gap or contract roll:
# levels inside the gap are skipped instead of filled.
GRID_GAP_SKIP = 2.0
# On the very first run, replay this many days of 5-minute bars.
GRID_BACKFILL_DAYS = 5

# --- Desk 3: Alpha ----------------------------------------------------------
ALPHA_WATCHLIST = [
    "XLE", "XOM", "CVX", "NVDA", "TSM", "MSFT",
    "PTTEP.BK", "PTT.BK", "DELTA.BK", "KBANK.BK", "CPALL.BK", "ADVANC.BK",
]
ALPHA_BENCHMARK = {"^GSPC": 0.5, "^SET50.BK": 0.5}
ALPHA_TOP_N = 3                # names held at once
ALPHA_LOOKBACK = 20            # trading days of momentum
ALPHA_BACKTEST_DAYS = 90       # history replayed before the first run
ALPHA_MOVER_ALERT_PCT = 2.0    # Scout reports daily moves at least this big

# --- HUD --------------------------------------------------------------------
MAX_DRAWDOWN_PCT = 10.0        # HP bar is empty at this drawdown
MONTHLY_TARGET_PCT = 1.5       # XP bar target, percent of starting capital

# Times on the dashboard are shown in this offset from UTC (Thailand = 7).
TZ_OFFSET_HOURS = 7
