# Inky Impression Weather Display

Raspberry Pi + Pimoroni Inky Impression 7.3" weather display. Renders an advice
card banner (what-to-wear, rain, storms, overnight, etc.) overlaid on a full-width
ensemble temperature graph. Fetches deterministic forecasts and condition icons
from Google Weather API, plus ensemble spread confidence, wind gusts, sunrise/sunset,
and US Air Quality Index from Open-Meteo (no API key required). Refreshes hourly via cron.

## Hardware
- Raspberry Pi (Pi 4 for dev, Pi Zero 2W recommended for the final install — needs a pre-soldered header)
- Pimoroni Inky Impression 7.3" (mounts on the 40-pin GPIO header)

## Setup (on the Pi)
1. Enable SPI and I2C: `sudo raspi-config` → Interface Options.
2. Free the SPI chip-select pin for the Inky library. On current Raspberry Pi OS
   (Bookworm), the kernel SPI driver claims GPIO8, and the `inky` library fails
   with `Chip Select: (line 8, GPIO8) currently claimed by spi0 CS0`. Add the
   `spi0-0cs` overlay (enables SPI0 with no kernel-managed chip-select lines) to
   `/boot/firmware/config.txt` (older images: `/boot/config.txt`), right after the
   existing `dtparam=spi=on` line — keep both:
   ```
   dtparam=spi=on
   dtoverlay=spi0-0cs
   ```
   Then `sudo reboot`.
3. Clone the repo and create a virtualenv:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Configure:
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

The Pi runs via `run.sh`, a wrapper that self-updates the checkout from
`origin/main` before each run, then renders. Make it executable once:
```bash
chmod +x run.sh
```
Add to crontab (`crontab -e`). `cron` sets `$HOME` to the crontab owner's home,
so `$HOME` keeps this correct whatever your username is — substitute a literal
absolute path only if you keep the repo elsewhere:
```
0 * * * * $HOME/inky_weather_odin/run.sh >> $HOME/weather.log 2>&1
```
The log path must be one the cron user can write. Pointing it at another user's
home (e.g. a hard-coded `/home/pi/...` when you run as a different user) makes the
shell fail to open the redirect, and the job never runs — the panel just goes
stale with nothing in the log.

### Auto-update

Each run, `run.sh`:
1. `git fetch` + `git reset --hard origin/main` — the Pi always matches the latest
   `main`. Your `config.py`, history, and cached image are gitignored, so the reset
   never touches them.
2. Reinstalls dependencies only if `requirements.txt` changed in that update.
3. If the network is down (fetch fails), it skips the update and runs the code
   already on disk — the display never goes dark over a failed pull.

It logs one line per run to `weather.log`, e.g
`… update: weather abc1234 -> def5678 (updated)` or `… (up to date)`.

Caveat: if a push changes `run.sh` itself, the new wrapper takes effect on the
*next* run (bash has already read the running copy).

### Versioning

The running version is `git describe --tags --always --dirty` — the short commit
SHA until you tag, then the tag name. It appears in the log line above and in the
top-right of the panel header (after the "updated" time). To cut a named release:
```bash
git tag v1.0.0 && git push --tags
```
After that the panel and log show `v1.0.0` (or e.g. `v1.0.0-3-gabc1234` three
commits later).

## Development (on a Mac)
Use a virtualenv (Homebrew/system Python blocks global `pip install` under
PEP 668 — the `externally-managed-environment` error):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install Pillow requests pytest      # NOT inky — it needs Pi-only GPIO libs
python3 -m pytest -v
python3 -m inky_weather.main --fixture --out fixture.out.png
```
The `inky` library is only needed on the Pi; it is imported lazily so tests and
`--out` rendering work without it. On the Pi, install everything with
`pip install -r requirements.txt` inside the venv (see Setup above).

### The PNG lies: design against the 7-colour palette

**A `--out` PNG is not what the panel shows.** `main.py` hands a full RGB image to
the `inky` library, which quantizes it to the panel's seven colours — black, white,
red, green, blue, yellow, orange. There is **no gray**. Any near-white tone snaps to
pure white and disappears on the hardware while looking perfect in the PNG.

This has already shipped a bug once: the precip reference lines used a faint gray
`(230, 231, 236)`, rendered correctly in every local preview and every test, and were
invisible on the device.

Rules for anything you draw:

- **Never encode meaning in lightness.** A "faint" or "subtle" element cannot be a
  pale colour. Get faintness from *coverage* instead — see `_dotted_line()` in
  `render.py`, which draws one pixel every three so a full-ink rule reads light.
- **Check any new colour constant against the palette** before using it. Add it to
  the guard in `test_gridlines_survive_seven_color_quantization`
  (`tests/test_smoke.py`) so a non-surviving colour fails the suite rather than
  shipping to the panel.
- **Known-invisible constants** still in `render.py`: `FAINT = (225, 226, 230)` and
  `COLOR_DRY = (210, 210, 210)`. Both quantize to white. Do not use them for
  anything load-bearing.

To preview what the panel will actually display, quantize the render yourself:

```bash
python3 -m inky_weather.main --fixture --out preview.png
python3 -c "
from PIL import Image
PANEL=[(0,0,0),(255,255,255),(0,255,0),(0,0,255),(255,0,0),(255,255,0),(255,140,0)]
im=Image.open('preview.png').convert('RGB')
q=Image.new('RGB',im.size)
q.putdata([min(PANEL,key=lambda p:sum((a-b)**2 for a,b in zip(p,c))) for c in im.getdata()])
q.save('panel_sim.png')"
```

Review `panel_sim.png`, not `preview.png`, when judging whether a visual change works.
