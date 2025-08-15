#!/usr/bin/env python3
"""
Smart Payment Verification System - Test Suite
Test script to validate SMS parsing, fraud detection, and system functionality
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test SMS samples for various scenarios
TEST_SMS_SAMPLES = [
    {
        "name": "MTN MoMo English",
        "text": "You have received RWF 5000 from John Doe +250788123456 on 15/08/2024 14:30. Ref: TX123456789",
        "expected": {"amount": 5000, "txid": "TX123456789", "sender_name": "John Doe"}
    },
    {
        "name": "MTN MoMo Kinyarwanda", 
        "text": "Wakiriye RWF 3500 kuva kwa Marie Uwimana +250789654321 ku 15/08/2024 10:15. Ref: TX987654321",
        "expected": {"amount": 3500, "txid": "TX987654321", "sender_name": "Marie Uwimana"}
    },
    {
        "name": "Airtel Money English",
        "text": "Payment of RWF 2000 received from Peter Nkusi +250788111222 on 15/08/2024 16:45. Reference: AM555666777",
        "expected": {"amount": 2000, "txid": "AM555666777", "sender_name": "Peter Nkusi"}
    },
    {
        "name": "Complex Format",
        "text": "Confirmed: You received RWF 15,000.00 from GASANA Claude (250-788-333-444) at 15/08/2024 09:20:15. Transaction ID: MT999888777",
        "expected": {"amount": 15000, "txid": "MT999888777", "sender_name": "GASANA Claude"}
    }
]

def test_sms_parsing():
    """Test SMS parsing functionality"""
    print("🔍 Testing SMS Parsing...")
    
    try:
        # Test with basic parser first
        from ml_models.sms_parser import parse_sms as basic_parse
        print("✅ Basic SMS parser imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import basic SMS parser: {e}")
        return False
    
    try:
        # Test with advanced parser
        from ml_models.advanced_sms_parser import parse_sms as advanced_parse
        print("✅ Advanced SMS parser imported successfully")
        use_advanced = True
    except ImportError:
        print("⚠️ Advanced SMS parser not available, using basic parser")
        use_advanced = False
    
    parser = advanced_parse if use_advanced else basic_parse
    
    passed_tests = 0
    total_tests = len(TEST_SMS_SAMPLES)
    
    for test in TEST_SMS_SAMPLES:
        print(f"\n📱 Testing: {test['name']}")
        print(f"SMS: {test['text']}")
        
        result = parser(test['text'])
        
        if result:
            print(f"✅ Parsed successfully:")
            print(f"   Amount: {result.get('amount')} (expected: {test['expected']['amount']})")
            print(f"   TxID: {result.get('txid')} (expected: {test['expected']['txid']})")
            print(f"   Name: {result.get('sender_name')} (expected: {test['expected']['sender_name']})")
            print(f"   Confidence: {result.get('confidence', 'N/A')}")
            
            # Check if key fields match expectations
            if (result.get('amount') == test['expected']['amount'] and 
                result.get('txid') == test['expected']['txid']):
                passed_tests += 1
                print("✅ Test PASSED")
            else:
                print("❌ Test FAILED - values don't match expectations")
        else:
            print("❌ Parsing failed")
    
    print(f"\n📊 SMS Parsing Results: {passed_tests}/{total_tests} tests passed")
    return passed_tests == total_tests

def test_fraud_detection():
    """Test fraud detection functionality"""
    print("\n🛡️ Testing Fraud Detection...")
    
    try:
        from ml_models.advanced_fraud_detector import detect_fraud
        print("✅ Advanced fraud detector imported successfully")
    except ImportError:
        try:
            from ml_models.fraud_detector import detect_fraud
            print("✅ Basic fraud detector imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import fraud detector: {e}")
            return False
    
    # Test cases for fraud detection
    test_cases = [
        {
            "name": "Legitimate Transaction",
            "transaction": {
                "txid": "TX123456789",
                "phone": "+250788123456",
                "name": "John Doe",
                "amount": 5000,
                "payment_data": {
                    "txid": "TX123456789",
                    "sender_number": "+250788123456",
                    "amount": 5000,
                    "timestamp": datetime.now().isoformat()
                }
            },
            "expected_risk": "low"
        },
        {
            "name": "Phone Mismatch (Suspicious)",
            "transaction": {
                "txid": "TX123456789",
                "phone": "+250788123456",
                "name": "John Doe",
                "amount": 5000,
                "payment_data": {
                    "txid": "TX123456789",
                    "sender_number": "+250788999999",  # Different phone
                    "amount": 5000,
                    "timestamp": datetime.now().isoformat()
                }
            },
            "expected_risk": "high"
        },
        {
            "name": "Amount Mismatch (Suspicious)",
            "transaction": {
                "txid": "TX123456789",
                "phone": "+250788123456",
                "name": "John Doe",
                "amount": 5000,
                "payment_data": {
                    "txid": "TX123456789",
                    "sender_number": "+250788123456",
                    "amount": 10000,  # Different amount
                    "timestamp": datetime.now().isoformat()
                }
            },
            "expected_risk": "high"
        }
    ]
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for test in test_cases:
        print(f"\n🔍 Testing: {test['name']}")
        
        try:
            result = detect_fraud(test['transaction'])
            fraud_score = result.get('fraud_score', 0)
            risk_level = result.get('risk_level', 'UNKNOWN').lower()
            
            print(f"   Fraud Score: {fraud_score:.2f}")
            print(f"   Risk Level: {risk_level}")
            print(f"   Expected: {test['expected_risk']} risk")
            
            # Simple risk assessment
            is_high_risk = fraud_score > 0.5
            expected_high_risk = test['expected_risk'] == 'high'
            
            if is_high_risk == expected_high_risk:
                passed_tests += 1
                print("✅ Test PASSED")
            else:
                print("❌ Test FAILED - risk assessment doesn't match expectation")
                
        except Exception as e:
            print(f"❌ Error during fraud detection: {e}")
    
    print(f"\n📊 Fraud Detection Results: {passed_tests}/{total_tests} tests passed")
    return passed_tests == total_tests

def test_system_health():
    """Test system health and basic functionality"""
    print("\n💚 Testing System Health...")
    
    try:
        # Test imports
        from app_enhanced import app, supabase, config
        print("✅ Main application imports successful")
        
        # Test configuration
        print(f"   Debug Mode: {config.DEBUG_MODE}")
        print(f"   Port: {config.PORT}")
        print(f"   Fraud Threshold: {config.FRAUD_THRESHOLD}")
        
        # Test database connection (if available)
        if supabase:
            print("✅ Supabase client initialized")
        else:
            print("⚠️ Supabase not configured (check .env file)")
            
        return True
        
    except Exception as e:
        print(f"❌ System health check failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints if server is running"""
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:10000"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health endpoint working")
            print(f"   Status: {health_data.get('status')}")
            print(f"   ML Models: {health_data.get('ml_models')}")
            print(f"   Database: {health_data.get('database_status')}")
        else:
            print(f"⚠️ Health endpoint returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠️ Server not running - skipping API endpoint tests")
        print("   Start the server with: python app_enhanced.py")
        return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False
    
    # Test SMS parsing endpoint (if debug mode)
    try:
        test_data = {
            "sms_text": "You have received RWF 5000 from John Doe +250788123456 on 15/08/2024 14:30. Ref: TX123456789"
        }
        
        response = requests.post(
            f"{base_url}/api/test/sms", 
            json=test_data,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SMS parsing endpoint working")
            print(f"   Parsed Amount: {result.get('parsed_data', {}).get('amount')}")
            print(f"   Parsed TxID: {result.get('parsed_data', {}).get('txid')}")
        else:
            print(f"⚠️ SMS parsing endpoint returned status {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ SMS parsing endpoint test failed: {e}")
    
    return True

def main():
    """Run all tests"""
    print("🚀 Smart Payment Verification System - Test Suite")
    print("="*60)
    
    test_results = []
    
    # Run individual tests
    test_results.append(("System Health", test_system_health()))
    test_results.append(("SMS Parsing", test_sms_parsing()))
    test_results.append(("Fraud Detection", test_fraud_detection()))
    test_results.append(("API Endpoints", test_api_endpoints()))
    
    # Print summary
    print("\n" + "="*60)
    print("📋 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall Results: {passed}/{total} test categories passed")
    
    if passed == total:
        print("🎉 All tests passed! Your system is ready for deployment.")
        return 0
    else:
        print("⚠️ Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    exit(main())
