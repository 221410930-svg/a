#!/usr/bin/env python3
"""
Test script to verify deployment readiness
"""
import os
import sys
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import streamlit
        import pandas
        import numpy
        import plotly
        import nixtla
        print("✅ All dependencies imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_files():
    """Test that all required files exist"""
    required_files = [
        "app.py",
        "dashboard.py", 
        "timegpt_model.py",
        "requirements.txt",
        "Detailed_dataset/nixtla_y__voltage_1_stack.csv"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_api_key():
    """Test that API key is set"""
    api_key = os.getenv("NIXTLA_API_KEY")
    if not api_key:
        print("⚠️  NIXTLA_API_KEY not set (required for deployment)")
        return False
    else:
        print("✅ NIXTLA_API_KEY is set")
        return True

def test_data_file():
    """Test that data file can be read"""
    try:
        import pandas as pd
        df = pd.read_csv("Detailed_dataset/nixtla_y__voltage_1_stack.csv")
        if len(df) < 60:
            print("⚠️  Data file has less than 60 points (may affect predictions)")
            return False
        print(f"✅ Data file loaded successfully ({len(df)} rows)")
        return True
    except Exception as e:
        print(f"❌ Error reading data file: {e}")
        return False

def main():
    print("🧪 Testing deployment readiness...\n")
    
    tests = [
        ("Dependencies", test_imports),
        ("Required Files", test_files),
        ("API Key", test_api_key),
        ("Data File", test_data_file)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Testing {test_name}...")
        result = test_func()
        results.append(result)
        print()
    
    if all(results):
        print("🎉 All tests passed! Your app is ready for deployment.")
        print("\nNext steps:")
        print("1. Set NIXTLA_API_KEY environment variable")
        print("2. Push to GitHub")
        print("3. Deploy on Streamlit Cloud")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
