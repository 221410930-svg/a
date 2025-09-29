#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local launcher for the Hydrogen Electrolyzer Dashboard"""
import os, subprocess, sys
from pathlib import Path

def main():
    print("🚀 Starting Hydrogen Electrolyzer Dashboard")
    for f in ["dashboard.py", "timegpt_model.py", "requirements.txt"]:
        if not Path(f).exists():
            print(f"❌ Missing {f}.")
            sys.exit(1)

    if not os.getenv("NIXTLA_API_KEY"):
        print("❌ NIXTLA_API_KEY environment variable is required.")
        print("Please set your TimeGPT API key: export NIXTLA_API_KEY=your_api_key_here")
        sys.exit(1)
    
    print("🔑 Using TimeGPT API")
    print("Open http://localhost:8501 (Ctrl+C to stop)")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py",
                    "--server.address", "localhost", "--server.port", "8501"])

if __name__ == "__main__":
    main()
