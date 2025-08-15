from Levenshtein import distance as levenshtein_distance
import re

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
