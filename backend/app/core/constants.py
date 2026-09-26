from datetime import date, timedelta

STANDARD_DEPTHS = [
    0.0,
    5.0,
    10.0,
    20.0,
    30.0,
    50.0,
    75.0,
    100.0,
    125.0,
    150.0,
    200.0,
    300.0,
    500.0,
    700.0,
    1000.0,
]

MODEL_LATITUDE_MIN = 5.0
MODEL_LATITUDE_MAX = 30.0
MODEL_LONGITUDE_MIN = 45.0
MODEL_LONGITUDE_MAX = 105.0
MODEL_LATITUDE_RESOLUTION = 0.25
MODEL_LONGITUDE_RESOLUTION = 0.25
MODEL_GRID_ROWS = 101
MODEL_GRID_COLS = 241
MODEL_DATE_START = date(2020, 1, 1)
MODEL_DATE_END = date(2020, 3, 31)

MODEL_AVAILABLE_DATES = []
_current_date = MODEL_DATE_START
while _current_date <= MODEL_DATE_END:
    MODEL_AVAILABLE_DATES.append(_current_date)
    _current_date += timedelta(days=1)
