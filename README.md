# Hydrogen Electrolyzer Monitor (Pro)

**Features**
- Historical voltage (blue), TimeGPT prediction (red dashed), 95% CI (pink)
- Real-time auto-refresh with configurable cadence
- 2-hour horizon by default
- CI-derived failure probability (principled normal tail)
- Robust to missing API (demo fallback)

## Run
```bash
cd h2_pro_dashboard
pip install -r requirements.txt
# optional: export NIXTLA_API_KEY=...
python app.py
```

## Data
Default path: `/mnt/data/nixtla_y__voltage_1_stack.csv` (auto-detected).
Units auto-detected (mV→V). Modify the candidates list in `timegpt_model.py` for a custom path.