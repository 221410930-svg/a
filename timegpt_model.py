#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TimeGPT wrapper for Hydrogen Electrolyzer voltage prediction.
- Reads last contiguous non‑zero window (with context padding)
- Converts mV → V automatically
- Produces 2h (120 min) horizon with 95% CI
- Computes failure probability using CI‑derived sigma (normal tail)
- Falls back gracefully to a realistic demo when TimeGPT is unavailable
"""
from __future__ import annotations

import os
from typing import Optional, List
from datetime import datetime, timedelta
from math import erf, sqrt

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class TimeGPTModel:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NIXTLA_API_KEY")
        self.client = None
        self.demo_mode = True
        
        if not self.api_key:
            raise ValueError("NIXTLA_API_KEY environment variable is required. Please set your TimeGPT API key.")
        
        try:
            from nixtla import NixtlaClient  # type: ignore
            self.client = NixtlaClient(api_key=self.api_key)
            try:
                self.client.validate_api_key()
                self.demo_mode = False
                print("✅ TimeGPT API connected successfully")
            except Exception as e:
                raise ValueError(f"TimeGPT API key validation failed: {e}. Please check your API key.")
        except Exception as e:
            raise ValueError(f"Nixtla SDK not available: {e}. Please install the nixtla package.")

    # ------------------ Data ------------------
    def load_voltage_data(
        self,
        data_path: str = None,
        value_col: str = "y",
        time_col: str = "ds",
        max_points: int = 4000,
        pad_minutes: int = 180,
    ) -> pd.DataFrame:
        """
        Load CSV, extract the most recent contiguous non-zero streak (with context pad),
        convert to volts if needed, and normalize to 1‑minute cadence.
        Returns DataFrame[['ds','y']].
        """
        if data_path is None:
            candidates = [
                "/mnt/data/nixtla_y__voltage_1_stack.csv",
                "Detailed_dataset/nixtla_y__voltage_1_stack.csv",
                "./Detailed_dataset/nixtla_y__voltage_1_stack.csv",
                os.path.join(os.getcwd(), "Detailed_dataset", "nixtla_y__voltage_1_stack.csv"),
            ]
            for p in candidates:
                if os.path.exists(p):
                    data_path = p
                    break
            if data_path is None:
                raise FileNotFoundError("Could not find nixtla_y__voltage_1_stack.csv in expected locations.")

        df = pd.read_csv(data_path)
        if time_col not in df or value_col not in df:
            raise ValueError(f"CSV must have columns '{time_col}' and '{value_col}'")

        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col, value_col]).sort_values(time_col).reset_index(drop=True)

        vals = df[value_col].to_numpy()
        nz_idx = np.flatnonzero(vals > 0)
        if nz_idx.size == 0:
            raise ValueError("No non-zero voltage data found.")

        # Last contiguous non-zero streak
        end = int(nz_idx[-1])
        start = end
        while start > 0 and vals[start - 1] > 0:
            start -= 1
        streak = df.iloc[start:end+1].copy()

        # Context pad BEFORE the streak start (avoid trailing shutdown zeros)
        start_time = streak[time_col].iloc[0] - timedelta(minutes=pad_minutes)
        end_time = streak[time_col].iloc[-1]
        window = df[(df[time_col] >= start_time) & (df[time_col] <= end_time)].copy()
        if window.empty:
            window = df.tail(max_points).copy()

        if len(window) > max_points:
            window = window.tail(max_points).copy()

        # Units: mV → V when median is clearly large
        y = window[value_col].astype(float).to_numpy()
        if np.nanmedian(y) > 100:  # robust to spikes; 500–650 → mV
            y = y / 1000.0
        window[value_col] = y

        out = window[[time_col, value_col]].rename(columns={time_col: "ds", value_col: "y"})
        out = (
            out.set_index("ds")
               .resample("1min")
               .mean()
               .interpolate(limit=5)  # small gaps only
               .reset_index()
               .dropna()
        )
        return out

    # ------------------ Forecast ------------------
    def predict(
        self,
        historical_data: pd.DataFrame,
        horizon_minutes: int = 120,         # 2 hours
        critical_threshold_v: float = 0.60, # good default for 0.5–0.65 V regime
    ) -> pd.DataFrame:
        """Return df with: ds, TimeGPT, TimeGPT-lo-95, TimeGPT-hi-95, failure_probability."""
        if self.demo_mode:
            raise ValueError("Demo mode is not available. Please provide a valid NIXTLA_API_KEY.")
        try:
            return self._timegpt_forecast(historical_data, horizon_minutes, critical_threshold_v)
        except Exception as e:
            raise ValueError(f"TimeGPT forecast error: {e}")

    def _timegpt_forecast(
        self, historical_data: pd.DataFrame, horizon_minutes: int, critical_threshold_v: float
    ) -> pd.DataFrame:
        """Use TimeGPT for a clean 1‑minute series with a full 120‑minute horizon."""
        df = (
            historical_data.copy()
            .set_index("ds").resample("1min").mean().interpolate(limit=5).reset_index().dropna()
        )

        if len(df) < 60:
            raise ValueError(f"Insufficient samples ({len(df)}) after cleaning; need ≥ 60 minutes.")

        # Mild IQR clipping for stability on short horizons
        y = df["y"].to_numpy()
        q1, q3 = np.nanpercentile(y, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 2.0 * iqr, q3 + 2.0 * iqr
        df = df[(df["y"] >= lo) & (df["y"] <= hi)]

        # Ensure proper time series format for TimeGPT
        df = df.copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)
        
        # Remove any duplicate timestamps
        df = df.drop_duplicates(subset=["ds"]).reset_index(drop=True)
        
        # Ensure continuous time series by filling gaps
        df = df.set_index("ds").resample("1min").mean().interpolate(method="linear", limit=5).reset_index()
        df = df.dropna()

        # Future‑proof: include unique_id
        df["unique_id"] = "electrolyzer_1"
        forecast = self.client.forecast(
            df=df[["unique_id", "ds", "y"]],
            h=horizon_minutes,
            freq="1min",
            level=[95],
        )

        # Normalize column names
        rename_map = {
            "yhat": "TimeGPT",
            "yhat_lower_95": "TimeGPT-lo-95",
            "yhat_upper_95": "TimeGPT-hi-95",
        }
        forecast = forecast.rename(columns={k: v for k, v in rename_map.items() if k in forecast.columns})

        need = {"ds", "TimeGPT", "TimeGPT-lo-95", "TimeGPT-hi-95"}
        missing = list(need - set(forecast.columns))
        if missing:
            raise ValueError(f"TimeGPT response missing columns: {missing}")

        forecast["failure_probability"] = self._failure_probs_ci(
            forecast["TimeGPT"].to_numpy(),
            critical_threshold_v,
            forecast["TimeGPT-hi-95"].to_numpy(),
        )
        return forecast[["ds", "TimeGPT", "TimeGPT-lo-95", "TimeGPT-hi-95", "failure_probability"]]

    def _demo_forecast(self, historical_data: pd.DataFrame, horizon_minutes: int, critical_threshold_v: float) -> pd.DataFrame:
        """
        Smooth demo around last value (~0.5–0.65 V), mild sinusoidal drift + noise, with 95% CI.
        CI width adapts to recent volatility.
        """
        last_time = pd.to_datetime(historical_data["ds"].iloc[-1])
        last_val  = float(historical_data["y"].iloc[-1])

        # Volatility-adaptive sigma
        hist_window = historical_data["y"].tail(min(240, len(historical_data)))  # last 4h if available
        hist_std = float(hist_window.std() or 0.006)
        sigma = float(np.clip(0.6 * hist_std, 0.004, 0.012))  # keep bands plausible

        rng = np.random.default_rng(int(datetime.now().timestamp()) % 1_000_000)
        times = pd.date_range(start=last_time, periods=horizon_minutes + 1, freq="1min")[1:]

        vals = []
        v = last_val
        for i in range(horizon_minutes):
            drift = 0.0015 * np.sin(2 * np.pi * (i / 60.0))      # ~60‑min gentle cycle
            v = float(np.clip(v + drift + rng.normal(0, 0.0018), 0.45, 0.70))
            vals.append(v)

        vals = np.array(vals, dtype=float)
        lo95 = (vals - 1.96 * sigma).clip(0.40, 0.75)
        hi95 = (vals + 1.96 * sigma).clip(0.40, 0.75)

        probs = self._failure_probs_ci(vals, critical_threshold_v, hi95)

        return pd.DataFrame({
            "ds": times,
            "TimeGPT": vals,
            "TimeGPT-lo-95": lo95,
            "TimeGPT-hi-95": hi95,
            "failure_probability": probs,
        })

    # ------------------ Probability helpers ------------------
    def _failure_probs_ci(self, mean: np.ndarray, threshold: float, upper_95: np.ndarray) -> List[float]:
        """
        Use CI to infer sigma: sigma ≈ (upper95 - mean) / 1.96
        Then P(Y ≥ threshold) = 1 - Φ((threshold - mean)/sigma)
        """
        mean = np.asarray(mean, dtype=float)
        upper_95 = np.asarray(upper_95, dtype=float)
        sigma = (upper_95 - mean) / 1.96
        sigma = np.clip(sigma, 1e-6, None)  # numeric safety

        z = (threshold - mean) / sigma
        # Φ(z) ≈ 0.5 * (1 + erf(z / √2))
        # Use numpy's vectorized erf function
        Phi = 0.5 * (1.0 + np.vectorize(erf)(z / sqrt(2.0)))
        probs = 1.0 - Phi
        return np.clip(probs, 0.0, 1.0).tolist()

    def get_model_status(self) -> dict:
        return {"demo_mode": self.demo_mode, "api_available": not self.demo_mode}