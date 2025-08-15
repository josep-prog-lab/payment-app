import re
from difflib import SequenceMatcher

def levenshtein_distance(a, b):
    """Pure Python Levenshtein distance calculation"""
    if len(a) < len(b):
        return levenshtein_distance(b, a)
    if len(b) == 0:
        return len(a)
    previous_row = range(len(b) + 1)
    for i, c1 in enumerate(a):
        current_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def similarity_ratio(a, b):
    """Calculate similarity ratio (0.0 to 1.0) between two strings"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    
    distance = levenshtein_distance(a.lower(), b.lower())
    max_len = max(len(a), len(b))
    return 1.0 - (distance / max_len)

def match_transaction(customer_txid, customer_phone, customer_amount, all_payments):
    """Fuzzy match a customer's TxID to received payments"""
    best_match = None
    best_score = -1
    suggestions = []
    
    # Clean customer phone
    customer_phone = re.sub(r'[^0-9]', '', customer_phone)
    if customer_phone.startswith('0'):
        customer_phone = '250' + customer_phone[1:]
    elif customer_phone.startswith('+250'):
        customer_phone = customer_phone[1:]
    
    for payment in all_payments:
        # Clean payment phone
        payment_phone = re.sub(r'[^0-9]', '', payment.get('sender_number', ''))
        if payment_phone.startswith('0'):
            payment_phone = '250' + payment_phone[1:]
        elif payment_phone.startswith('+250'):
            payment_phone = payment_phone[1:]
        
        # Calculate similarity scores
        txid_sim = 1 - (levenshtein_distance(customer_txid.lower(), payment.get('txid', '').lower()) / max(len(customer_txid), len(payment.get('txid', '')), 1))
        phone_sim = 1 if customer_phone == payment_phone else 0
        
        # Amount similarity (if amount was provided)
        if customer_amount:
            amount_diff = abs(float(customer_amount) - float(payment.get('amount', 0)))
            amount_sim = 1 - (amount_diff / max(float(customer_amount), float(payment.get('amount', 1)), 1))
        else:
            amount_sim = 0.5  # Neutral score if amount not provided
        
        # Combined score (weighted)
        combined_score = (txid_sim * 0.6) + (phone_sim * 0.3) + (amount_sim * 0.1)
        
        # Track best match
        if combined_score > best_score:
            best_score = combined_score
            best_match = payment
        
        # Collect suggestions above threshold
        if combined_score > 0.5:
            suggestions.append({
                'txid': payment.get('txid'),
                'amount': payment.get('amount'),
                'timestamp': payment.get('timestamp'),
                'confidence': combined_score
            })
    
    return {
        'payment': best_match,
        'confidence': best_score,
        'suggestions': sorted(suggestions, key=lambda x: x['confidence'], reverse=True)[:3]
    }
