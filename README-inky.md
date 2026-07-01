# Inky Impression Weather Display

Raspberry Pi + Pimoroni Inky Impression 7.3" weather display. Fetches Google
Maps Platform Weather forecasts and renders a 12-hour hourly panel plus a
10-day strip. Refreshes hourly via cron.

## Hardware
- Raspberry Pi (Pi 4 for dev, Pi Zero 2W recommended for the final install — needs a pre-soldered header)
- Pimoroni Inky Impression 7.3" (mounts on the 40-pin GPIO header)

## Setup (on the Pi)
1. Enable SPI and I2C: `sudo raspi-config` → Interface Options.
2. Clone the repo and create a virtualenv:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure:
   ```bash
   cp inky_weather/config.example.py inky_weather/config.py
   # edit config.py: google_weather_key, lat, long, location_name
   ```

## Test
- Offline render to PNG (no display needed):
  ```bash
  python3 -m inky_weather.main --fixture --out test.png
  ```
- Live fetch to the display:
  ```bash
  python3 -m inky_weather.main
  ```

## Schedule (hourly refresh)
Add to crontab (`crontab -e`), using the venv's Python:
```
0 * * * * cd /home/pi/magtag_weather_odin && /home/pi/magtag_weather_odin/.venv/bin/python -m inky_weather.main >> /home/pi/weather.log 2>&1
```

## Development (on a Mac)
```bash
pip install Pillow requests pytest
python3 -m pytest -v
python3 -m inky_weather.main --fixture --out fixture.out.png
```
The `inky` library is only needed on the Pi; it is imported lazily so tests and
`--out` rendering work without it.
