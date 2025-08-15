import os
import logging
import traceback
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import re
import json
import psutil
from typing import Dict, List, Optional

# Import our ML models - with fallbacks for legacy support
try:
    from ml_models.advanced_sms_parser import parse_sms
    from ml_models.advanced_fraud_detector import detect_fraud
    from ml_models.advanced_matcher import match_transaction_advanced as match_transaction
    ADVANCED_ML = True
except ImportError:
    # Fallback to basic models
    from ml_models.sms_parser import parse_sms
    from ml_models.fraud_detector import detect_fraud
    from ml_models.matcher import match_transaction
    ADVANCED_ML = False
    print("Warning: Using basic ML models. Install advanced dependencies for better performance.")

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Configure logging
log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('payment_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Supabase client with error handling
try:
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing Supabase credentials")
    
    supabase: Client = create_client(supabase_url, supabase_key)
    logger.info("Successfully connected to Supabase")
except Exception as e:
    logger.error(f"Failed to initialize Supabase: {e}")
    supabase = None

# Application configuration
class Config:
    SMS_FORWARDER_SECRET = os.getenv('SMS_FORWARDER_SECRET')
    SMS_FORWARDER_NUMBER = os.getenv('SMS_FORWARDER_NUMBER')
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', 10000))
    MAX_VERIFICATION_AGE = int(os.getenv('MAX_VERIFICATION_AGE', 24))  # hours
    FRAUD_THRESHOLD = float(os.getenv('FRAUD_THRESHOLD', 0.7))

config = Config()

# Utility functions
def log_api_call(endpoint: str, method: str, status_code: int, response_time_ms: int, 
                 company_id: str = None, request_data: Dict = None):
    """Log API calls for monitoring and analytics"""
    if not supabase:
        return
    
    try:
        supabase.table('api_logs').insert({
            'company_id': company_id,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_time_ms': response_time_ms,
            'request_data': request_data or {},
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log API call: {e}")

def validate_request_data(data: Dict, required_fields: List[str]) -> Optional[str]:
    """Validate required fields in request data"""
    for field in required_fields:
        if not data.get(field):
            return f"Missing required field: {field}"
    return None

def get_company_by_secret(secret: str) -> Optional[Dict]:
    """Get company information by webhook secret"""
    if not supabase:
        return None
    
    try:
        result = supabase.table('companies').select('*').eq('webhook_secret', secret).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error getting company by secret: {e}")
        return None

def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to international format"""
    phone = re.sub(r'[^0-9+]', '', phone)
    if phone.startswith('0'):
        return '+250' + phone[1:]
    elif phone.startswith('250'):
        return '+' + phone
    elif not phone.startswith('+'):
        return '+' + phone
    return phone

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    logger.error(traceback.format_exc())
    return jsonify({'error': 'An unexpected error occurred'}), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    start_time = datetime.now()
    
    health_status = {
        'status': 'healthy',
        'timestamp': start_time.isoformat(),
        'version': '1.0.0',
        'ml_models': 'advanced' if ADVANCED_ML else 'basic',
        'database_status': 'connected' if supabase else 'disconnected',
        'system_info': {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
    }
    
    # Test database connection
    if supabase:
        try:
            supabase.table('companies').select('id').limit(1).execute()
            health_status['database_test'] = 'passed'
        except Exception as e:
            health_status['database_test'] = f'failed: {e}'
            health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    response_time = int((datetime.now() - start_time).total_seconds() * 1000)
    
    log_api_call('/health', 'GET', status_code, response_time)
    
    return jsonify(health_status), status_code

# Main page
@app.route('/')
def index():
    """Main payment verification page"""
    return render_template('index.html')

@app.route('/api/docs')
def api_docs():
    """API documentation page"""
    return render_template('api_docs.html')

# SMS receiving endpoint
@app.route('/api/sms', methods=['POST'])
def receive_sms():
    """Receive SMS from forwarder app"""
    start_time = datetime.now()
    
    try:
        # Validate request
        if not supabase:
            return jsonify({'error': 'Database not available'}), 503
        
        # Check authentication
        secret = request.headers.get('X-Forwarder-Secret')
        if not secret:
            logger.warning("SMS request without secret header")
            return jsonify({'error': 'Missing authentication header'}), 401
        
        company = get_company_by_secret(secret)
        if not company:
            logger.warning(f"SMS request with invalid secret: {secret}")
            return jsonify({'error': 'Invalid authentication'}), 401
        
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        validation_error = validate_request_data(data, ['text', 'from'])
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        sms_text = data.get('text')
        sender_number = normalize_phone_number(data.get('from'))
        
        logger.info(f"Received SMS from {sender_number} for company {company['name']}")
        
        # Parse SMS using ML models
        parsed_data = parse_sms(sms_text)
        
        if not parsed_data:
            logger.warning(f"Failed to parse SMS: {sms_text[:100]}...")
            return jsonify({'error': 'Failed to parse SMS'}), 400
        
        # Store parsed payment in database
        payment_record = {
            'company_id': company['id'],
            'sender_number': sender_number,
            'sms_text': sms_text,
            'amount': parsed_data.get('amount'),
            'txid': parsed_data.get('txid'),
            'sender_name': parsed_data.get('sender_name'),
            'timestamp': parsed_data.get('timestamp'),
            'parsed_data': parsed_data,
            'parsing_confidence': parsed_data.get('confidence', 0.8),
            'status': 'unverified'
        }
        
        result = supabase.table('received_payments').insert(payment_record).execute()
        
        if result.data:
            payment_id = result.data[0]['id']
            logger.info(f"Stored payment {payment_id} successfully")
            
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            log_api_call('/api/sms', 'POST', 200, response_time, company['id'], {
                'sender_number': sender_number,
                'amount': parsed_data.get('amount'),
                'txid': parsed_data.get('txid')
            })
            
            return jsonify({
                'success': True, 
                'id': payment_id,
                'parsed_amount': parsed_data.get('amount'),
                'parsed_txid': parsed_data.get('txid'),
                'confidence': parsed_data.get('confidence', 0.8)
            }), 200
        else:
            raise Exception("Failed to insert payment record")
            
    except Exception as e:
        logger.error(f"Error processing SMS: {e}")
        logger.error(traceback.format_exc())
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_call('/api/sms', 'POST', 500, response_time)
        return jsonify({'error': 'Internal server error'}), 500

# Payment verification endpoint
@app.route('/api/verify', methods=['POST'])
def verify_payment():
    """Verify customer payment against received SMS"""
    start_time = datetime.now()
    
    try:
        if not supabase:
            return jsonify({'error': 'Database not available'}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        # Validate required fields
        validation_error = validate_request_data(data, ['txid', 'phone', 'name'])
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        txid = data.get('txid').strip()
        phone = normalize_phone_number(data.get('phone'))
        name = data.get('name').strip()
        amount = data.get('amount')
        
        logger.info(f"Payment verification request: TxID={txid}, Phone={phone}, Name={name}")
        
        # Get company (for now, use default company)
        company_result = supabase.table('companies').select('*').limit(1).execute()
        if not company_result.data:
            return jsonify({'error': 'No company configured'}), 500
        
        company = company_result.data[0]
        company_id = company['id']
        
        # Create verification record
        verification_data = {
            'company_id': company_id,
            'customer_name': name,
            'customer_phone': phone,
            'submitted_txid': txid,
            'submitted_amount': float(amount) if amount else None,
            'verification_status': 'pending'
        }
        
        verification_result = supabase.table('payment_verifications').insert(verification_data).execute()
        verification_id = verification_result.data[0]['id']
        
        # Find matching payment using exact match first
        payment_query = supabase.table('received_payments').select('*').eq('txid', txid)
        if company_id:
            payment_query = payment_query.eq('company_id', company_id)
        
        payment_result = payment_query.execute()
        matched_payment = None
        match_confidence = 0.0
        
        if payment_result.data:
            matched_payment = payment_result.data[0]
            match_confidence = 1.0
            logger.info(f"Found exact TxID match: {matched_payment['id']}")
        else:
            # Try fuzzy matching if exact match not found
            logger.info("No exact match found, trying fuzzy matching...")
            all_payments_result = supabase.table('received_payments').select('*').eq('company_id', company_id).eq('status', 'unverified').execute()
            
            if all_payments_result.data:
                match_result = match_transaction(txid, phone, amount, all_payments_result.data)
                
                if match_result and match_result.get('confidence', 0) >= 0.7:
                    matched_payment = match_result['payment']
                    match_confidence = match_result['confidence']
                    logger.info(f"Found fuzzy match with confidence {match_confidence}")
        
        if not matched_payment:
            # Update verification as failed
            supabase.table('payment_verifications').update({
                'verification_status': 'failed',
                'match_confidence': 0.0,
                'verification_details': {'error': 'No matching transaction found'}
            }).eq('id', verification_id).execute()
            
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            log_api_call('/api/verify', 'POST', 200, response_time, company_id, {
                'txid': txid, 'result': 'failed'
            })
            
            return jsonify({
                'verified': False,
                'message': 'No matching transaction found',
                'suggestions': match_result.get('suggestions', []) if 'match_result' in locals() else []
            }), 200
        
        # Run fraud detection
        transaction_data = {
            'txid': txid,
            'phone': phone,
            'name': name,
            'amount': amount,
            'payment_data': matched_payment
        }
        
        # Get payment history for behavioral analysis
        history_result = supabase.table('payment_verifications').select('*').eq('company_id', company_id).limit(50).execute()
        payment_history = history_result.data or []
        
        fraud_result = detect_fraud(transaction_data, payment_history)
        fraud_score = fraud_result.get('fraud_score', 0.0)
        risk_level = fraud_result.get('risk_level', 'UNKNOWN')
        
        logger.info(f"Fraud analysis: Score={fraud_score}, Risk={risk_level}")
        
        # Determine verification status
        if fraud_score >= config.FRAUD_THRESHOLD:
            verification_status = 'suspicious' if fraud_score < 0.9 else 'manual_review'
            verified = False
        else:
            verification_status = 'verified'
            verified = True
            
            # Update payment status
            supabase.table('received_payments').update({
                'status': 'verified',
                'fraud_score': fraud_score
            }).eq('id', matched_payment['id']).execute()
        
        # Update verification record
        update_data = {
            'payment_id': matched_payment['id'],
            'verification_status': verification_status,
            'match_confidence': match_confidence,
            'fraud_risk': fraud_score,
            'verification_details': {
                'fraud_analysis': fraud_result,
                'matched_payment_id': matched_payment['id'],
                'matching_method': 'exact' if match_confidence == 1.0 else 'fuzzy'
            },
            'verified_at': datetime.now().isoformat() if verified else None
        }
        
        supabase.table('payment_verifications').update(update_data).eq('id', verification_id).execute()
        
        # Log fraud detection if applicable
        if fraud_result.get('rule_violations'):
            supabase.table('fraud_logs').insert({
                'verification_id': verification_id,
                'fraud_type': 'rule_violations',
                'risk_score': fraud_score,
                'details': fraud_result,
                'ml_model_version': '1.0'
            }).execute()
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_call('/api/verify', 'POST', 200, response_time, company_id, {
            'txid': txid, 'result': verification_status, 'fraud_score': fraud_score
        })
        
        response_data = {
            'verified': verified,
            'verification_id': verification_id,
            'match_confidence': match_confidence,
            'fraud_risk': fraud_score,
            'risk_level': risk_level,
            'amount': matched_payment['amount'],
            'timestamp': matched_payment['timestamp'],
            'recommendation': fraud_result.get('recommendation', '')
        }
        
        if not verified:
            response_data.update({
                'message': f'Transaction flagged as {risk_level.lower()} risk',
                'fraud_details': fraud_result.get('details', {}),
                'rule_violations': fraud_result.get('rule_violations', [])
            })
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in payment verification: {e}")
        logger.error(traceback.format_exc())
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_call('/api/verify', 'POST', 500, response_time)
        return jsonify({'error': 'Internal server error'}), 500

# Admin dashboard endpoints
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard for monitoring transactions"""
    return render_template('admin_dashboard.html')

@app.route('/api/admin/stats')
def admin_stats():
    """Get dashboard statistics"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not available'}), 503
        
        # Get basic statistics
        stats = {}
        
        # Total payments received today
        today = datetime.now().date()
        payments_today = supabase.table('received_payments').select('*').gte('created_at', today.isoformat()).execute()
        stats['payments_today'] = len(payments_today.data)
        
        # Verification statistics
        verifications = supabase.table('payment_verifications').select('*').gte('created_at', today.isoformat()).execute()
        stats['verifications_today'] = len(verifications.data)
        
        # Status breakdown
        status_counts = {}
        for verification in verifications.data:
            status = verification['verification_status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        stats['status_breakdown'] = status_counts
        
        # Fraud statistics
        high_risk_count = sum(1 for v in verifications.data if v.get('fraud_risk', 0) > 0.7)
        stats['high_risk_transactions'] = high_risk_count
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/transactions')
def admin_transactions():
    """Get recent transactions for admin dashboard"""
    try:
        if not supabase:
            return jsonify({'error': 'Database not available'}), 503
        
        limit = request.args.get('limit', 50, type=int)
        
        # Get recent verifications with payment details
        verifications = supabase.table('payment_verifications').select('*, received_payments(*)').order('created_at', desc=True).limit(limit).execute()
        
        return jsonify(verifications.data), 200
        
    except Exception as e:
        logger.error(f"Error getting admin transactions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Test endpoint for SMS simulation
@app.route('/api/test/sms', methods=['POST'])
def test_sms():
    """Test endpoint for SMS simulation (development only)"""
    if not config.DEBUG_MODE:
        return jsonify({'error': 'Test endpoints disabled in production'}), 403
    
    data = request.get_json()
    sample_sms = data.get('sms_text', 'You have received RWF 5000 from John Doe +250788123456 on 15/08/2024 14:30. Ref: TX123456789')
    
    parsed = parse_sms(sample_sms)
    return jsonify({
        'original_sms': sample_sms,
        'parsed_data': parsed,
        'ml_version': 'advanced' if ADVANCED_ML else 'basic'
    })

if __name__ == '__main__':
    logger.info(f"Starting Smart Payment Verification System")
    logger.info(f"ML Models: {'Advanced' if ADVANCED_ML else 'Basic'}")
    logger.info(f"Database: {'Connected' if supabase else 'Disconnected'}")
    logger.info(f"Debug Mode: {config.DEBUG_MODE}")
    
    app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG_MODE
    )
