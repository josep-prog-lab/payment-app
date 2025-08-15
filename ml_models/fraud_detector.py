"""
Lightweight Fraud Detection System
Uses statistical methods and rule-based detection instead of complex ML models
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import hashlib


class FraudDetector:
    def __init__(self):
        self.max_amount_threshold = 500000  # 500k RWF
        self.suspicious_patterns = [
            r'test', r'fake', r'fraud', r'scam', r'dummy'
        ]
        self.common_fraud_indicators = [
            'repeated_txid', 'amount_mismatch', 'time_anomaly', 
            'suspicious_name', 'invalid_phone', 'duplicate_submission'
        ]
        
    def calculate_risk_score(self, transaction_data: Dict) -> Tuple[float, List[str]]:
        """
        Calculate fraud risk score based on multiple factors
        Returns: (risk_score, risk_factors)
        """
        risk_score = 0.0
        risk_factors = []
        
        # Check amount anomalies
        amount = transaction_data.get('amount', 0)
        if amount > self.max_amount_threshold:
            risk_score += 0.3
            risk_factors.append('high_amount')
        elif amount <= 0:
            risk_score += 0.5
            risk_factors.append('invalid_amount')
            
        # Check TxID patterns
        txid = transaction_data.get('txid', '').upper()
        if self.is_suspicious_txid(txid):
            risk_score += 0.4
            risk_factors.append('suspicious_txid')
            
        # Check name patterns
        name = transaction_data.get('name', '').lower()
        if self.is_suspicious_name(name):
            risk_score += 0.2
            risk_factors.append('suspicious_name')
            
        # Check phone number validity
        phone = transaction_data.get('phone', '')
        if not self.is_valid_phone(phone):
            risk_score += 0.2
            risk_factors.append('invalid_phone')
            
        # Check for duplicate submissions
        if self.check_duplicate_risk(transaction_data):
            risk_score += 0.6
            risk_factors.append('duplicate_submission')
            
        # Check time anomalies
        if self.check_time_anomaly(transaction_data):
            risk_score += 0.3
            risk_factors.append('time_anomaly')
            
        return min(risk_score, 1.0), risk_factors
    
    def is_suspicious_txid(self, txid: str) -> bool:
        """Check if TxID follows suspicious patterns"""
        if not txid or len(txid) < 6:
            return True
            
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if pattern in txid.lower():
                return True
                
        # Check for sequential or repeated characters
        if len(set(txid)) < 3:  # Too few unique characters
            return True
            
        # Check for obviously fake patterns
        if re.match(r'^(123|ABC|TEST|FAKE)', txid, re.IGNORECASE):
            return True
            
        return False
    
    def is_suspicious_name(self, name: str) -> bool:
        """Check if name contains suspicious patterns"""
        if not name:
            return False
            
        # Check for test/fake names
        for pattern in self.suspicious_patterns:
            if pattern in name.lower():
                return True
                
        # Check for obviously fake names
        fake_patterns = [r'^test', r'^fake', r'^dummy', r'admin', r'user\d+']
        for pattern in fake_patterns:
            if re.search(pattern, name.lower()):
                return True
                
        return False
    
    def is_valid_phone(self, phone: str) -> bool:
        """Validate Rwanda phone number format"""
        if not phone:
            return False
            
        # Remove non-digits
        digits = re.sub(r'[^\d]', '', phone)
        
        # Check Rwanda phone number patterns
        if digits.startswith('250'):
            return len(digits) == 12 and digits[3:6] in ['78', '79', '72', '73']
        elif digits.startswith('0'):
            return len(digits) == 10 and digits[1:3] in ['78', '79', '72', '73']
        elif len(digits) == 9:
            return digits[0:2] in ['78', '79', '72', '73']
            
        return False
    
    def check_duplicate_risk(self, transaction_data: Dict) -> bool:
        """Check for potential duplicate submissions"""
        # This would typically check against database history
        # For now, we'll use a simple hash-based check
        txid = transaction_data.get('txid', '')
        phone = transaction_data.get('phone', '')
        amount = transaction_data.get('amount', 0)
        
        # Create a transaction fingerprint
        fingerprint = hashlib.md5(
            f"{txid}{phone}{amount}".encode()
        ).hexdigest()
        
        # In production, check this fingerprint against recent submissions
        # For MVP, we'll flag if TxID is too short (likely fake)
        return len(txid) < 8
    
    def check_time_anomaly(self, transaction_data: Dict) -> bool:
        """Check for time-based anomalies"""
        # Check if transaction is claimed too quickly (within 30 seconds)
        # This would be implemented with actual timing data in production
        return False  # Placeholder for MVP
    
    def detect_fraud(self, transaction_data: Dict) -> Dict:
        """
        Main fraud detection function
        """
        risk_score, risk_factors = self.calculate_risk_score(transaction_data)
        
        # Determine risk level
        if risk_score >= 0.8:
            risk_level = 'HIGH'
            action = 'block'
        elif risk_score >= 0.5:
            risk_level = 'MEDIUM'
            action = 'review'
        elif risk_score >= 0.3:
            risk_level = 'LOW'
            action = 'flag'
        else:
            risk_level = 'MINIMAL'
            action = 'approve'
            
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'recommended_action': action,
            'timestamp': datetime.now().isoformat()
        }


# Global detector instance
_detector = FraudDetector()

def detect_fraud(transaction_data: Dict) -> float:
    """
    Public function to detect fraud and return risk score
    """
    result = _detector.detect_fraud(transaction_data)
    return result['risk_score']
