"""Pixel Trading Floor: paper-trading desks fed by live public market data.

Three desks, each run on paper money against real prices:

- ``roc``   Return on Cash  - idle cash earning the 13-week T-bill rate
- ``grid``  Beta / Oil Grid - a long-only WTI grid replayed on 5-minute bars
- ``alpha`` Alpha           - weekly momentum picks vs. a SPX/SET50 benchmark

``python -m floor`` updates the state file and writes the dashboard's
``data.json``. Settings live in ``floor/config.py``.
"""
