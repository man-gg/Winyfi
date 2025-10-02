#!/usr/bin/env python3
"""
Test script for PDF generation endpoints
"""

import requests
import os
from datetime import datetime, timedelta

def test_pdf_endpoints():
    """Test the PDF generation endpoints"""
    base_url = "http://localhost:5000"
    
    # Test parameters
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    mode = "weekly"
    
    print("Testing PDF generation endpoints...")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Mode: {mode}")
    print("-" * 50)
    
    # Test 1: Basic PDF endpoint
    print("1. Testing basic PDF endpoint...")
    try:
        response = requests.get(f"{base_url}/api/reports/pdf", 
                              params={
                                  "start_date": start_date,
                                  "end_date": end_date,
                                  "mode": mode
                              },
                              timeout=30)
        
        if response.status_code == 200:
            # Save the PDF
            filename = f"test_basic_report_{start_date}_to_{end_date}.pdf"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"✅ Basic PDF generated successfully: {filename}")
            print(f"   File size: {len(response.content)} bytes")
        else:
            print(f"❌ Basic PDF failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Basic PDF error: {e}")
    
    print()
    
    # Test 2: PDF with charts endpoint
    print("2. Testing PDF with charts endpoint...")
    try:
        response = requests.get(f"{base_url}/api/reports/pdf-with-charts", 
                              params={
                                  "start_date": start_date,
                                  "end_date": end_date,
                                  "mode": mode
                              },
                              timeout=30)
        
        if response.status_code == 200:
            # Save the PDF
            filename = f"test_charts_report_{start_date}_to_{end_date}.pdf"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"✅ PDF with charts generated successfully: {filename}")
            print(f"   File size: {len(response.content)} bytes")
        else:
            print(f"❌ PDF with charts failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ PDF with charts error: {e}")
    
    print()
    print("Test completed!")

if __name__ == "__main__":
    test_pdf_endpoints()

