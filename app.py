#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hydrogen Electrolyzer Dashboard - Streamlit Cloud Entry Point
This file serves as the main entry point for Streamlit Cloud deployment.
"""
import os
import sys
from pathlib import Path

# Check for required files
required_files = ["timegpt_model.py", "Detailed_dataset/nixtla_y__voltage_1_stack.csv"]
missing_files = [f for f in required_files if not Path(f).exists()]

if missing_files:
    import streamlit as st
    st.error(f"❌ Missing required files: {missing_files}")
    st.stop()

# Check for API key
if not os.getenv("NIXTLA_API_KEY"):
    import streamlit as st
    st.error("❌ NIXTLA_API_KEY environment variable is required.")
    st.info("Please set your TimeGPT API key in the Streamlit Cloud secrets.")
    st.stop()

# Import and run the dashboard
try:
    from dashboard import main
    main()
except Exception as e:
    import streamlit as st
    st.error(f"❌ Error loading dashboard: {e}")
    st.exception(e)