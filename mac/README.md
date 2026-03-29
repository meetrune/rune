# Mac Training Workstation (v5+)

This directory will contain code for the MacBook Pro M3 Max training workstation.

## What Goes Here (v5)

- **LSTM autoencoder training** via MLX (Apple Silicon optimized)
- **Prophet fuel forecasting** -- predict fill-up dates and fuel costs
- **Route clustering** -- identify driving patterns and route segments
- **Seasonal calibration** -- adjust baselines for temperature/humidity
- **PDF report generation** -- Jinja2 + matplotlib + WeasyPrint

## How It Works

1. Export SQLite DB from Pi (weekly/monthly, whenever convenient)
2. Run training scripts on Mac
3. Output: TFLite model + JSON configs + PDF reports
4. Deploy artifacts back to Pi (makes real-time inference smarter)

## Hardware

MacBook Pro M3 Max, 36GB unified memory.

See PRD Section 11 (v5) for full specification.
