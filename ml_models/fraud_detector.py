from sklearn.ensemble import IsolationForest
import numpy as np
import joblib
from datetime import datetime
import os
import re

# In a real implementation, we would load a pre-trained model
# For this example, we'll create a simple rule-based detector with ML capabilities

class FraudDetector:
    def __init__(self):
        # In production, we would load a trained model
        # self.model = joblib.load('fraud_model.pkl')
        self.model = IsolationForest(contamination=0.05, random_state=42)
        self.features = None
        
    def extract_features(self, transaction):
        """Convert transaction data to numerical features"""
        # Simple features - would be enhanced in production
        features = {
            'amount': float(transaction.get('amount', 0)),
            'time_since_last_tx': 0,  # Would calculate from history
            'phone_in_contacts': 0,    # Would check against known contacts
            'name_length': len(transaction.get('name', '')),
            'txid_length': len(transaction.get('txid', '')),
            'hour_of_day': datetime.fromisoformat(transaction['payment_data']['timestamp']).hour if 'payment_data' in transaction else 0,
            'amount_deviation': 0,    # Would compare to typical amounts
            'typo_score': self.calculate_typo_score(transaction)
        }
        return list(features.values())
    
    def calculate_typo_score(self, transaction):
        """Score based on potential typos in name or TxID"""
        name = transaction.get('name', '').lower()
        txid = transaction.get('txid', '')
        
        # Check for repeated characters (potential fake TxIDs)
        repeat_score = sum(1 for i in range(len(txid)-1) if txid[i] == txid[i+1]) / len(txid) if txid else 0
        
        # Check name formatting
        name_score = 0
        if name:
            parts = name.split()
            if len(parts) < 2:  # Likely needs first and last name
                name_score += 0.3
            if any(len(part) < 2 for part in parts):
                name_score += 0.2
                
        return repeat_score + name_score
    
    def detect(self, transaction):
        """Detect potential fraud in a transaction"""
        # Rule-based checks
        rules_violated = 0
        
        # 1. Check if TxID matches exactly
        if transaction.get('txid') != transaction['payment_data'].get('txid'):
            rules_violated += 1
        
        # 2. Check if phone numbers match
        customer_phone = re.sub(r'[^0-9]', '', transaction.get('phone', ''))
        sms_phone = re.sub(r'[^0-9]', '', transaction['payment_data'].get('sender_number', ''))
        
        if customer_phone != sms_phone:
            rules_violated += 1
        
        # 3. Check amount (if provided)
        if 'amount' in transaction and abs(float(transaction['amount']) - float(transaction['payment_data'].get('amount', 0))) > 100:
            rules_violated += 1
        
        # ML-based detection
        features = self.extract_features(transaction)
        ml_score = self.model.predict([features])[0]  # -1 for outlier, 1 for inlier
        
        # Combine rule-based and ML scores
        total_score = (rules_violated / 3) * 0.6  # 60% weight to rules
        total_score += (0 if ml_score == 1 else 1) * 0.4  # 40% weight to ML
        
        return total_score

# Global instance
detector = FraudDetector()

def detect_fraud(transaction):
    """Public interface for fraud detection"""
    return detector.detect(transaction)
