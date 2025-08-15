import os
from flask import Flask, request, jsonify, render_template
from supabase import create_client, Client
from dotenv import load_dotenv
from ml_models.sms_parser import parse_sms
from ml_models.fraud_detector import detect_fraud
from ml_models.matcher import match_transaction
import re

load_dotenv()

app = Flask(__name__)

# Initialize Supabase
supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

@app.route('/')
def index():
    return render_template('index.html')

# Endpoint for SMS forwarder app
@app.route('/api/sms', methods=['POST'])
def receive_sms():
    # Verify the request comes from our forwarder
    if request.headers.get('X-Forwarder-Secret') != os.getenv('SMS_FORWARDER_SECRET'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    sms_text = data.get('text')
    sender_number = data.get('from')
    
    if not sms_text or not sender_number:
        return jsonify({'error': 'Missing SMS text or sender number'}), 400
    
    # Parse SMS using ML model
    parsed_data = parse_sms(sms_text)
    
    if not parsed_data:
        return jsonify({'error': 'Failed to parse SMS'}), 400
    
    # Store in Supabase
    try:
        res = supabase.table('received_payments').insert({
            'sender_number': sender_number,
            'sms_text': sms_text,
            'amount': parsed_data['amount'],
            'txid': parsed_data['txid'],
            'timestamp': parsed_data['timestamp'],
            'parsed_data': parsed_data,
            'status': 'unverified'
        }).execute()
        return jsonify({'success': True, 'id': res.data[0]['id']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint for customer TxID submission
@app.route('/api/verify', methods=['POST'])
def verify_payment():
    data = request.json
    txid = data.get('txid')
    phone = data.get('phone')
    name = data.get('name')
    amount = data.get('amount')
    
    if not all([txid, phone, name]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Clean phone number format
    phone = re.sub(r'[^0-9]', '', phone)
    if phone.startswith('0'):
        phone = '250' + phone[1:]
    elif phone.startswith('+250'):
        phone = phone[1:]
    
    # Find matching payment in database
    try:
        res = supabase.table('received_payments').select('*').eq('txid', txid).execute()
        
        if len(res.data) == 0:
            # Try fuzzy matching if exact match not found
            res = supabase.table('received_payments').select('*').execute()
            all_payments = res.data
            best_match = match_transaction(txid, phone, amount, all_payments)
            
            if best_match['confidence'] < 0.7:  # Threshold for acceptance
                return jsonify({
                    'verified': False,
                    'message': 'No matching transaction found',
                    'suggestions': best_match.get('suggestions', [])
                }), 200
            
            matched_payment = best_match['payment']
        else:
            matched_payment = res.data[0]
        
        # Fraud detection
        fraud_score = detect_fraud({
            'txid': txid,
            'phone': phone,
            'name': name,
            'amount': amount,
            'payment_data': matched_payment
        })
        
        # Update status in database
        supabase.table('received_payments').update({
            'status': 'verified',
            'customer_name': name,
            'customer_phone': phone,
            'fraud_score': fraud_score
        }).eq('id', matched_payment['id']).execute()
        
        return jsonify({
            'verified': True,
            'fraud_risk': fraud_score,
            'amount': matched_payment['amount'],
            'timestamp': matched_payment['timestamp']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=int(os.getenv('PORT', 10000)))
