"""
Smart Payment Verification System
Lightweight Flask API for Rwanda MoMo payment verification
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
from ml_models.sms_parser import parse_sms
from ml_models.fraud_detector import detect_fraud
from ml_models.matcher import match_transaction
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Initialize Supabase client
try:
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if supabase_url and supabase_key:
        try:
            # Try with new supabase client parameters
            supabase: Client = create_client(supabase_url, supabase_key)
            # Test the connection
            supabase.table('received_payments').select('id').limit(1).execute()
            logger.info("Successfully connected to Supabase")
        except Exception as client_error:
            logger.warning(f"Supabase connection issue: {client_error}")
            logger.info("Running in offline mode - database features disabled")
            supabase = None
    else:
        logger.info("Supabase credentials not provided - running in offline mode")
        supabase = None
except Exception as e:
    logger.error(f"Failed to initialize Supabase: {e}")
    supabase = None

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
    
    # Store in Supabase (if available)
    if not supabase:
        return jsonify({
            'success': True,
            'message': 'SMS parsed successfully (offline mode)',
            'parsed_data': parsed_data
        }), 200
    
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
        logger.error(f"Database error: {e}")
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
    
    # Offline mode demo - return success with fraud check
    if not supabase:
        fraud_score = detect_fraud({
            'txid': txid,
            'phone': phone,
            'name': name,
            'amount': amount or 50000
        })
        
        return jsonify({
            'verified': True,
            'fraud_risk': fraud_score,
            'amount': amount or 50000,
            'timestamp': datetime.now().isoformat(),
            'message': 'Demo mode - database not connected'
        }), 200
    
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
        logger.error(f"Error verifying payment: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        # Test database connection
        if supabase:
            supabase.table('received_payments').select('id').limit(1).execute()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected' if supabase else 'disconnected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/status/<transaction_id>')
def get_transaction_status(transaction_id):
    """Get status of a specific transaction"""
    try:
        res = supabase.table('received_payments').select('*').eq('id', transaction_id).execute()
        
        if len(res.data) == 0:
            return jsonify({'error': 'Transaction not found'}), 404
            
        transaction = res.data[0]
        return jsonify({
            'id': transaction['id'],
            'status': transaction['status'],
            'amount': transaction['amount'],
            'txid': transaction['txid'],
            'timestamp': transaction['timestamp'],
            'fraud_score': transaction.get('fraud_score', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting transaction status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def get_system_stats():
    """Get system statistics for admin dashboard"""
    
    # Offline mode - return demo stats
    if not supabase:
        return jsonify({
            'total_transactions': 42,
            'recent_transactions': 8,
            'verified_transactions': 38,
            'verification_rate': 90.5,
            'timestamp': datetime.now().isoformat(),
            'message': 'Demo stats - database not connected'
        }), 200
    
    try:
        # Get stats from last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        
        # Total transactions
        total_res = supabase.table('received_payments').select('id').execute()
        total_count = len(total_res.data)
        
        # Recent transactions
        recent_res = supabase.table('received_payments').select('*').gte('created_at', yesterday).execute()
        recent_count = len(recent_res.data)
        
        # Verified transactions
        verified_res = supabase.table('received_payments').select('id').eq('status', 'verified').execute()
        verified_count = len(verified_res.data)
        
        return jsonify({
            'total_transactions': total_count,
            'recent_transactions': recent_count,
            'verified_transactions': verified_count,
            'verification_rate': (verified_count / max(total_count, 1)) * 100,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


# Development/Testing endpoints
if os.getenv('ENABLE_TEST_ENDPOINTS') == 'True':
    @app.route('/api/test/parse', methods=['POST'])
    def test_parse_sms():
        """Test SMS parsing endpoint"""
        data = request.json
        sms_text = data.get('text')
        
        if not sms_text:
            return jsonify({'error': 'Missing SMS text'}), 400
            
        parsed = parse_sms(sms_text)
        return jsonify({
            'input': sms_text,
            'parsed': parsed,
            'success': parsed is not None
        }), 200
    
    @app.route('/api/test/fraud', methods=['POST'])
    def test_fraud_detection():
        """Test fraud detection endpoint"""
        data = request.json
        
        fraud_score = detect_fraud(data)
        return jsonify({
            'input': data,
            'fraud_score': fraud_score,
            'risk_level': 'HIGH' if fraud_score > 0.7 else 'MEDIUM' if fraud_score > 0.4 else 'LOW'
        }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    debug = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    
    logger.info(f"Starting Smart Payment Verification System on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
