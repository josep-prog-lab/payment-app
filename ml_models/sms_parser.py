"""
Smart SMS Parser for Rwanda Mobile Money Transactions
Uses regex patterns and string matching for efficient parsing without heavy ML dependencies
"""

import re
from datetime import datetime
from typing import Dict, Optional, List
try:
    from unidecode import unidecode
except ImportError:
    def unidecode(text):
        return text


class SMSParser:
    def __init__(self):
        # Common MoMo SMS patterns for Rwanda (MTN, Airtel, Tigo)
        self.patterns = {
            'mtn_payment': [
                r'Transaction ID:\s*([A-Z0-9]+)',
                r'Ref\.\s*([A-Z0-9]+)',
                r'Reference:\s*([A-Z0-9]+)',
                r'TxnID:\s*([A-Z0-9]+)',
                r'(?:Ref|Reference|No)\s?[:.]?\s?([A-Z0-9]{6,15})',
            ],
            'amount': [
                r'RWF\s*([\d,]+\.?\d*)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*RWF',
                r'Amount:\s*RWF\s*([\d,]+\.?\d*)',
                r'(\d+(?:,\d{3})*)\s*Rwf',
                r'received\s+(?:RWF\s*)?(\d+(?:,\d{3})*)',
                r'recu\s+(?:RWF\s*)?(\d+(?:,\d{3})*)',
                r'wakiriye\s+(?:RWF\s*)?(\d+(?:,\d{3})*)',
            ],
            'phone': [
                r'(\+?250\d{9})',
                r'(0\d{9})',
                r'(\d{9})',
                r'to\s*(\+?250\d{9})',
                r'from\s*(\+?250\d{9})',
                r'kuva\s*(\+?250\d{9})',
                r'de\s*(\+?250\d{9})',
            ],
            'name': [
                r'from\s+([A-Za-z\s]+)\s+(?:\(|\+)',
                r'kuva\s+([A-Za-z\s]+)\s+(?:\(|\+)',
                r'de\s+([A-Za-z\s]+)\s+(?:\(|\+)',
                r'Name:\s*([A-Za-z\s]+)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)',
            ],
        }

    def clean_amount(self, amount_str: str) -> Optional[float]:
        """Clean and convert amount string to float"""
        if not amount_str:
            return None
        
        # Remove commas and spaces
        cleaned = re.sub(r'[,\s]', '', amount_str)
        try:
            return float(cleaned)
        except ValueError:
            return None

    def clean_phone(self, phone: str) -> Optional[str]:
        """Standardize phone number format"""
        if not phone:
            return None
        
        # Remove all non-digits
        digits_only = re.sub(r'[^\d]', '', phone)
        
        # Convert to international format
        if digits_only.startswith('250'):
            return digits_only
        elif digits_only.startswith('0') and len(digits_only) == 10:
            return '250' + digits_only[1:]
        elif len(digits_only) == 9:
            return '250' + digits_only
        
        return digits_only if len(digits_only) >= 9 else None

    def clean_name(self, name: str) -> Optional[str]:
        """Clean and standardize name"""
        if not name:
            return None
        
        # Remove extra spaces and normalize
        cleaned = re.sub(r'\s+', ' ', name.strip())
        # Convert to ASCII to handle special characters
        cleaned = unidecode(cleaned)
        
        return cleaned if len(cleaned) > 2 else None

    def extract_txid(self, text: str) -> Optional[str]:
        """Extract transaction ID using multiple patterns"""
        for pattern in self.patterns['mtn_payment']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                txid = match.group(1).strip()
                if len(txid) >= 6:  # Minimum TxID length
                    return txid.upper()
        return None

    def extract_amount(self, text: str) -> Optional[float]:
        """Extract amount using multiple patterns"""
        for pattern in self.patterns['amount']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self.clean_amount(match.group(1))
                if amount and amount > 0:
                    return amount
        return None

    def extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number using multiple patterns"""
        for pattern in self.patterns['phone']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = self.clean_phone(match.group(1))
                if phone:
                    return phone
        return None

    def extract_name(self, text: str) -> Optional[str]:
        """Extract name using multiple patterns"""
        for pattern in self.patterns['name']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self.clean_name(match.group(1))
                if name:
                    return name
        return None

    def parse_sms(self, sms_text: str) -> Optional[Dict]:
        """
        Main parsing function that extracts all relevant information
        """
        if not sms_text:
            return None

        # Clean the SMS text
        text = sms_text.strip()
        
        # Check if this looks like a payment SMS
        payment_keywords = ['transaction', 'payment', 'transfer', 'rwf', 'airtel money', 'mtn mobile money', 'tigo cash', 'received', 'recu', 'wakiriye']
        if not any(keyword in text.lower() for keyword in payment_keywords):
            return None

        # Extract information
        txid = self.extract_txid(text)
        amount = self.extract_amount(text)
        phone = self.extract_phone(text)
        name = self.extract_name(text)
        
        # Must have at least TxID and amount to be valid
        if not txid or not amount:
            return None

        parsed_data = {
            'txid': txid,
            'amount': amount,
            'phone': phone,
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'raw_text': sms_text,
            'confidence': self.calculate_confidence(txid, amount, phone, name)
        }

        return parsed_data

    def calculate_confidence(self, txid: str, amount: float, phone: str, name: str) -> float:
        """Calculate parsing confidence score"""
        score = 0.0
        
        if txid and len(txid) >= 8:
            score += 0.4
        elif txid:
            score += 0.2
            
        if amount and amount > 0:
            score += 0.3
            
        if phone:
            score += 0.2
            
        if name and len(name) > 2:
            score += 0.1
            
        return min(score, 1.0)


# Global parser instance
_parser = SMSParser()

def parse_sms(sms_text: str) -> Optional[Dict]:
    """
    Public function to parse SMS text
    """
    return _parser.parse_sms(sms_text)
