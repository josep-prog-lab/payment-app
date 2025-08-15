import re
import json
import spacy
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

# Try to load spacy model, fall back to simple parsing if not available
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    print("Warning: spaCy model not found. Using rule-based parsing only.")

class AdvancedSMSParser:
    def __init__(self):
        self.momo_patterns = {
            'english': [
                r'(?i)(?:you have )?received (?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) from ([^0-9]+) (\+?\d{10,15}).*?on (\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?ref[:\.]? ?(\w+)',
                r'(?i)(?:payment of )?(?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) received from ([^0-9]+) (\+?\d{10,15}).*?(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?(?:reference|ref|id)[:\.]? ?(\w+)',
            ],
            'kinyarwanda': [
                r'(?i)(?:wakiriye )?(?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) kuva (?:kwa )?([^0-9]+) (\+?\d{10,15}).*?ku (\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?ref[:\.]? ?(\w+)',
                r'(?i)(?:kwishyura )?(?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) (?:kuva|kwa) ([^0-9]+) (\+?\d{10,15}).*?(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?(?:nimero|ref)[:\.]? ?(\w+)',
            ],
            'french': [
                r'(?i)(?:vous avez )?reçu (?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) de ([^0-9]+) (\+?\d{10,15}).*?le (\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?(?:référence|ref)[:\.]? ?(\w+)',
                r'(?i)(?:paiement de )?(?:rwf )?(\d+(?:,\d{3})*(?:\.\d{2})?) reçu de ([^0-9]+) (\+?\d{10,15}).*?(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}).*?(?:référence|ref|id)[:\.]? ?(\w+)',
            ]
        }
        
        # Load or initialize ML models
        self.tfidf_vectorizer = None
        self.entity_classifier = None
        self.load_models()
    
    def load_models(self):
        """Load pre-trained ML models if available"""
        try:
            model_dir = os.path.join(os.path.dirname(__file__), 'models')
            if os.path.exists(os.path.join(model_dir, 'tfidf_vectorizer.pkl')):
                self.tfidf_vectorizer = joblib.load(os.path.join(model_dir, 'tfidf_vectorizer.pkl'))
            if os.path.exists(os.path.join(model_dir, 'entity_classifier.pkl')):
                self.entity_classifier = joblib.load(os.path.join(model_dir, 'entity_classifier.pkl'))
        except Exception as e:
            print(f"Warning: Could not load ML models: {e}")
    
    def parse_sms(self, sms_text: str) -> Optional[Dict]:
        """
        Parse MoMo SMS using hybrid approach: regex + NLP + ML
        """
        # First try regex patterns
        regex_result = self._regex_parse(sms_text)
        if regex_result and regex_result.get('confidence', 0) > 0.8:
            return regex_result
        
        # Try NLP parsing with spaCy
        if nlp:
            nlp_result = self._nlp_parse(sms_text)
            if nlp_result and nlp_result.get('confidence', 0) > 0.7:
                return nlp_result
        
        # Fallback to ML-based parsing
        ml_result = self._ml_parse(sms_text)
        return ml_result
    
    def _regex_parse(self, sms_text: str) -> Optional[Dict]:
        """Parse SMS using regex patterns"""
        for language, patterns in self.momo_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, sms_text, re.IGNORECASE | re.DOTALL)
                if match:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        sender_name = match.group(2).strip()
                        sender_number = self._normalize_phone(match.group(3))
                        timestamp_str = match.group(4)
                        txid = match.group(5).strip()
                        
                        # Parse timestamp
                        timestamp = self._parse_timestamp(timestamp_str)
                        
                        return {
                            'amount': amount,
                            'sender_name': self._clean_name(sender_name),
                            'sender_number': sender_number,
                            'timestamp': timestamp.isoformat() if timestamp else None,
                            'txid': txid,
                            'raw_text': sms_text,
                            'parsing_method': 'regex',
                            'language': language,
                            'confidence': 0.9
                        }
                    except Exception:
                        continue
        return None
    
    def _nlp_parse(self, sms_text: str) -> Optional[Dict]:
        """Parse SMS using spaCy NLP"""
        if not nlp:
            return None
        
        doc = nlp(sms_text)
        
        # Extract entities
        amount = self._extract_money(doc)
        phone_numbers = self._extract_phones(sms_text)
        names = self._extract_person_names(doc)
        timestamp = self._extract_timestamp(sms_text)
        txid = self._extract_transaction_id(sms_text)
        
        if amount and txid:
            return {
                'amount': amount,
                'sender_name': names[0] if names else None,
                'sender_number': phone_numbers[0] if phone_numbers else None,
                'timestamp': timestamp.isoformat() if timestamp else None,
                'txid': txid,
                'raw_text': sms_text,
                'parsing_method': 'nlp',
                'confidence': 0.8 if all([amount, txid, names, phone_numbers]) else 0.6
            }
        return None
    
    def _ml_parse(self, sms_text: str) -> Optional[Dict]:
        """Parse SMS using ML models"""
        # Basic fallback parsing
        amount = self._extract_amount_fallback(sms_text)
        phone = self._extract_phone_fallback(sms_text)
        timestamp = self._extract_timestamp(sms_text)
        txid = self._extract_txid_fallback(sms_text)
        name = self._extract_name_fallback(sms_text)
        
        confidence = 0.4
        if amount and txid:
            confidence = 0.6
        if amount and txid and phone:
            confidence = 0.7
        
        return {
            'amount': amount,
            'sender_name': name,
            'sender_number': phone,
            'timestamp': timestamp.isoformat() if timestamp else None,
            'txid': txid,
            'raw_text': sms_text,
            'parsing_method': 'ml_fallback',
            'confidence': confidence
        }
    
    def _extract_money(self, doc) -> Optional[float]:
        """Extract money amount using spaCy"""
        for ent in doc.ents:
            if ent.label_ == "MONEY":
                # Extract numeric value
                amount_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', ent.text)
                if amount_match:
                    return float(amount_match.group(1).replace(',', ''))
        
        # Fallback: look for RWF patterns
        money_patterns = [
            r'(?:rwf|frw)\s?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s?(?:rwf|frw)',
        ]
        
        for pattern in money_patterns:
            match = re.search(pattern, doc.text, re.IGNORECASE)
            if match:
                return float(match.group(1).replace(',', ''))
        
        return None
    
    def _extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers"""
        phone_pattern = r'(\+?250\d{9}|\+?\d{10,15})'
        phones = re.findall(phone_pattern, text)
        return [self._normalize_phone(phone) for phone in phones]
    
    def _extract_person_names(self, doc) -> List[str]:
        """Extract person names using spaCy"""
        names = []
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                names.append(ent.text.strip())
        return names
    
    def _extract_timestamp(self, text: str) -> Optional[datetime]:
        """Extract timestamp from various formats"""
        timestamp_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)',
            r'(\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)',
            r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)',
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, text)
            if match:
                return self._parse_timestamp(match.group(1))
        return None
    
    def _extract_transaction_id(self, text: str) -> Optional[str]:
        """Extract transaction ID"""
        txid_patterns = [
            r'(?:ref|reference|txid|transaction|id)[:\.\s]*([A-Z0-9]{8,20})',
            r'([A-Z0-9]{10,20})(?:\s|$)',  # Standalone alphanumeric strings
        ]
        
        for pattern in txid_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                txid = match.group(1).strip()
                if len(txid) >= 8:  # MoMo TxIDs are usually 8+ characters
                    return txid
        return None
    
    # Fallback extraction methods
    def _extract_amount_fallback(self, text: str) -> Optional[float]:
        """Fallback amount extraction"""
        patterns = [
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                amount = float(match.replace(',', ''))
                if 100 <= amount <= 10000000:  # Reasonable payment range
                    return amount
        return None
    
    def _extract_phone_fallback(self, text: str) -> Optional[str]:
        """Fallback phone extraction"""
        phone_pattern = r'(\+?\d{10,15})'
        phones = re.findall(phone_pattern, text)
        if phones:
            return self._normalize_phone(phones[0])
        return None
    
    def _extract_txid_fallback(self, text: str) -> Optional[str]:
        """Fallback TxID extraction"""
        # Look for sequences of letters and numbers
        txid_pattern = r'\b([A-Z0-9]{8,20})\b'
        matches = re.findall(txid_pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Filter out phone numbers and amounts
            if not re.match(r'^\d+$', match) and not re.match(r'^\+?\d{10,15}$', match):
                return match.upper()
        return None
    
    def _extract_name_fallback(self, text: str) -> Optional[str]:
        """Fallback name extraction"""
        # Look for capitalized words that could be names
        name_pattern = r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b'
        match = re.search(name_pattern, text)
        if match:
            return match.group(1).strip()
        return None
    
    # Utility methods
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format"""
        phone = re.sub(r'[^\d+]', '', phone)
        if phone.startswith('0'):
            return '+250' + phone[1:]
        elif phone.startswith('250'):
            return '+' + phone
        elif not phone.startswith('+'):
            return '+' + phone
        return phone
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize name"""
        # Remove common non-name words
        noise_words = ['from', 'to', 'mr', 'mrs', 'miss', 'dr']
        words = name.lower().split()
        cleaned_words = [w.title() for w in words if w.lower() not in noise_words and len(w) > 1]
        return ' '.join(cleaned_words[:3])  # Limit to 3 names max
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        formats = [
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%d-%m-%Y %H:%M',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        return None

# Global parser instance
parser = AdvancedSMSParser()

def parse_sms(sms_text: str) -> Optional[Dict]:
    """Public interface for SMS parsing"""
    return parser.parse_sms(sms_text)
