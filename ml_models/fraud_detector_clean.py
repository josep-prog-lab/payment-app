import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report
from datetime import datetime, timedelta
import joblib
import json
import re
import os
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleFraudDetector:
    def __init__(self):
        self.feature_columns = [
            'amount', 'hour_of_day', 'day_of_week', 'txid_length', 'name_length',
            'phone_match_score', 'amount_deviation', 'time_since_last_tx',
            'velocity_score', 'duplicate_txid_count', 'name_similarity_score',
            'amount_frequency_score', 'suspicious_patterns_score'
        ]
    
    def detect_fraud(self, transaction: Dict, payment_history: List[Dict] = None) -> Dict:
        """Main fraud detection method using simple rule-based approach"""
        # Rule-based checks
        rule_violations, rule_score = self.rule_based_checks(transaction)
        
        # Simple behavioral analysis
        behavioral_score = self.behavioral_analysis(transaction, payment_history or [])
        
        # Combine scores (simplified)
        final_score = (rule_score * 0.7) + (behavioral_score * 0.3)
        
        # Determine risk level
        if final_score >= 0.8:
            risk_level = 'HIGH'
        elif final_score >= 0.6:
            risk_level = 'MEDIUM'
        elif final_score >= 0.4:
            risk_level = 'LOW'
        else:
            risk_level = 'MINIMAL'
        
        return {
            'fraud_score': final_score,
            'risk_level': risk_level,
            'rule_violations': rule_violations,
            'behavioral_score': behavioral_score,
            'details': {
                'component_scores': {
                    'rules': rule_score,
                    'behavioral': behavioral_score
                },
                'violations': rule_violations
            },
            'recommendation': self.get_recommendation(final_score, risk_level)
        }
    
    def rule_based_checks(self, transaction: Dict) -> Tuple[List[str], float]:
        """Fast rule-based fraud checks"""
        violations = []
        score = 0.0
        
        # Check 1: Exact TxID match
        if transaction.get('txid') != transaction.get('payment_data', {}).get('txid'):
            violations.append('txid_mismatch')
            score += 0.4
        
        # Check 2: Phone number match
        customer_phone = self.normalize_phone(transaction.get('phone', ''))
        sms_phone = self.normalize_phone(transaction.get('payment_data', {}).get('sender_number', ''))
        if customer_phone != sms_phone:
            violations.append('phone_mismatch')
            score += 0.3
        
        # Check 3: Amount discrepancy
        if 'amount' in transaction and 'payment_data' in transaction:
            customer_amount = float(transaction.get('amount', 0))
            sms_amount = float(transaction.get('payment_data', {}).get('amount', 0))
            if abs(customer_amount - sms_amount) > 1000:  # Allow small discrepancy
                violations.append('amount_mismatch')
                score += 0.5
        
        # Check 4: Suspicious TxID patterns
        txid = transaction.get('txid', '')
        if self.is_suspicious_txid(txid):
            violations.append('suspicious_txid_pattern')
            score += 0.3
        
        # Check 5: Time-based checks
        if self.is_suspicious_timing(transaction):
            violations.append('suspicious_timing')
            score += 0.2
        
        return violations, min(score, 1.0)
    
    def behavioral_analysis(self, transaction: Dict, payment_history: List[Dict]) -> float:
        """Analyze behavioral patterns for fraud detection"""
        if not payment_history:
            return 0.3  # Neutral score for new customers
        
        behavioral_score = 0.0
        
        # Check for velocity (too many transactions in short time)
        recent_transactions = [
            tx for tx in payment_history 
            if self.is_recent_transaction(tx, hours=24)
        ]
        
        if len(recent_transactions) > 10:
            behavioral_score += 0.3
        elif len(recent_transactions) > 5:
            behavioral_score += 0.2
        
        # Check for duplicate patterns
        txids = [tx.get('txid', '') for tx in payment_history]
        if transaction.get('txid') in txids:
            behavioral_score += 0.4  # Reused TxID is very suspicious
        
        return min(behavioral_score, 1.0)
    
    def normalize_phone(self, phone: str) -> str:
        """Normalize phone number"""
        phone = re.sub(r'[^\d+]', '', phone)
        if phone.startswith('0'):
            return '+250' + phone[1:]
        elif phone.startswith('250'):
            return '+' + phone
        elif not phone.startswith('+'):
            return '+' + phone
        return phone
    
    def is_suspicious_txid(self, txid: str) -> bool:
        """Check if TxID has suspicious patterns"""
        if not txid or len(txid) < 6:
            return True
        
        # Check for repeated characters
        repeated_chars = sum(1 for i in range(len(txid)-1) if txid[i] == txid[i+1])
        if repeated_chars > len(txid) / 3:
            return True
        
        # Check for sequential patterns
        if re.match(r'^(012|123|234|345|456|567|678|789|890)+', txid):
            return True
        
        return False
    
    def is_suspicious_timing(self, transaction: Dict) -> bool:
        """Check for suspicious timing patterns"""
        if 'payment_data' not in transaction:
            return False
        
        try:
            timestamp = transaction['payment_data'].get('timestamp')
            if timestamp:
                tx_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour = tx_time.hour
                
                # Suspicious if transaction is very late at night
                if hour < 5 or hour > 23:
                    return True
        except:
            pass
        
        return False
    
    def is_recent_transaction(self, tx: Dict, hours: int) -> bool:
        """Check if transaction is within specified hours"""
        try:
            if 'created_at' in tx:
                tx_time = datetime.fromisoformat(tx['created_at'].replace('Z', '+00:00'))
                time_diff = (datetime.now() - tx_time).total_seconds() / 3600
                return time_diff <= hours
        except:
            pass
        return False
    
    def get_recommendation(self, score: float, risk_level: str) -> str:
        """Get recommendation based on fraud score"""
        if risk_level == 'HIGH':
            return 'REJECT - High fraud risk. Manual review required.'
        elif risk_level == 'MEDIUM':
            return 'REVIEW - Medium fraud risk. Additional verification recommended.'
        elif risk_level == 'LOW':
            return 'APPROVE - Low fraud risk. Transaction appears legitimate.'
        else:
            return 'APPROVE - Minimal fraud risk. Safe to process.'

# Global detector instance
detector = SimpleFraudDetector()

def detect_fraud(transaction: Dict, payment_history: List[Dict] = None) -> Dict:
    """Public interface for fraud detection"""
    return detector.detect_fraud(transaction, payment_history)
