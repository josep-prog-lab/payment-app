import re
from datetime import datetime
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')

def parse_sms(sms_text):
    """Parse MoMo payment SMS to extract key information using NLP and regex"""
    
    # Common MTN MoMo patterns in Rwanda
    patterns = [
        # English pattern
        r"(?:You have )?received(?: RWF)? (\d+(?:,\d{3})*(?:\.\d{2})?) from (\+\d{11,15}|[\w\s]+) (\+\d{11,15}).*?on (\d{2}/\d{2}/\d{4} \d{2}:\d{2}).*?Ref\.? (\w+)",
        # Kinyarwanda pattern
        r"(?:Wakiriye )?RWF (\d+(?:,\d{3})*(?:\.\d{2})?) kuva (\+\d{11,15}|[\w\s]+) (\+\d{11,15}).*?ku (\d{2}/\d{2}/\d{4} \d{2}:\d{2}).*?Ref\.? (\w+)",
        # French pattern
        r"(?:Vous avez )?recu(?: RWF)? (\d+(?:,\d{3})*(?:\.\d{2})?) de (\+\d{11,15}|[\w\s]+) (\+\d{11,15}).*?le (\d{2}/\d{2}/\d{4} \d{2}:\d{2}).*?Ref\.? (\w+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            amount = float(match.group(1).replace(',', ''))
            sender_name = match.group(2).strip()
            sender_number = match.group(3).strip()
            timestamp = datetime.strptime(match.group(4), '%d/%m/%Y %H:%M')
            txid = match.group(5).strip()
            
            # Clean sender name with NLP
            tokens = word_tokenize(sender_name)
            tagged = pos_tag(tokens)
            # Keep only proper nouns and nouns
            cleaned_name = ' '.join([word for word, pos in tagged if pos in ['NNP', 'NN']])
            
            return {
                'amount': amount,
                'sender_name': cleaned_name or sender_name,
                'sender_number': sender_number,
                'timestamp': timestamp.isoformat(),
                'txid': txid,
                'raw_text': sms_text
            }
    
    # Fallback to ML-based parsing if regex fails
    return ml_parse_sms(sms_text)

def ml_parse_sms(sms_text):
    """More advanced parsing using NLP techniques when regex fails"""
    # This would be enhanced with actual ML models in production
    # For MVP, we'll use a simple approach
    
    # Extract amount (look for RWF or numbers)
    amount_match = re.search(r'(?:RWF|Frw|FRW)\s?(\d+(?:,\d{3})*(?:\.\d{2})?)', sms_text, re.IGNORECASE)
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else None
    
    # Extract phone numbers
    phone_matches = re.findall(r'(\+\d{11,15})', sms_text)
    sender_phone = phone_matches[0] if phone_matches else None
    receiver_phone = phone_matches[1] if len(phone_matches) > 1 else None
    
    # Extract date
    date_match = re.search(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2})', sms_text)
    timestamp = datetime.strptime(date_match.group(1), '%d/%m/%Y %H:%M').isoformat() if date_match else None
    
    # Extract reference/TxID
    txid_matches = re.findall(r'(?:Ref|Reference|No)\s?[:.]?\s?(\w{8,15})', sms_text, re.IGNORECASE)
    txid = txid_matches[0] if txid_matches else None
    
    # Extract name using NLP
    tokens = word_tokenize(sms_text)
    tagged = pos_tag(tokens)
    # Find names (sequence of proper nouns)
    name_parts = []
    for word, pos in tagged:
        if pos == 'NNP':
            name_parts.append(word)
        elif name_parts:
            break
    
    sender_name = ' '.join(name_parts) if name_parts else None
    
    return {
        'amount': amount,
        'sender_name': sender_name,
        'sender_number': sender_phone,
        'timestamp': timestamp,
        'txid': txid,
        'raw_text': sms_text,
        'parsing_confidence': 0.7 if all([amount, txid]) else 0.4
    }
