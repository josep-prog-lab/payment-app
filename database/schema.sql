-- =============================================================================
-- Smart Payment Verification System - Database Schema
-- Run this SQL in your Supabase SQL editor to set up the database
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table to store received SMS payments
CREATE TABLE received_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_number VARCHAR(20) NOT NULL,
    sms_text TEXT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    txid VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    parsed_data JSONB,
    status VARCHAR(20) DEFAULT 'unverified',
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    fraud_score DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table to store verification attempts
CREATE TABLE verification_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id UUID REFERENCES received_payments(id),
    customer_txid VARCHAR(50) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    customer_amount DECIMAL(12,2),
    match_confidence DECIMAL(3,2),
    fraud_score DECIMAL(3,2),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table to track system metrics
CREATE TABLE system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(12,2) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX idx_received_payments_txid ON received_payments(txid);
CREATE INDEX idx_received_payments_status ON received_payments(status);
CREATE INDEX idx_received_payments_timestamp ON received_payments(timestamp DESC);
CREATE INDEX idx_verification_attempts_payment_id ON verification_attempts(payment_id);
CREATE INDEX idx_verification_attempts_timestamp ON verification_attempts(created_at DESC);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update timestamps
CREATE TRIGGER update_received_payments_updated_at 
    BEFORE UPDATE ON received_payments 
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Row Level Security (RLS) policies
ALTER TABLE received_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_metrics ENABLE ROW LEVEL SECURITY;

-- Allow service role to access all data
CREATE POLICY "Service role can access all payments" ON received_payments
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can access all verification attempts" ON verification_attempts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can access all metrics" ON system_metrics
    FOR ALL USING (auth.role() = 'service_role');

-- Anonymous role policies (for API access)
CREATE POLICY "API can read payments" ON received_payments
    FOR SELECT USING (true);

CREATE POLICY "API can insert payments" ON received_payments
    FOR INSERT WITH CHECK (true);

CREATE POLICY "API can update payments" ON received_payments
    FOR UPDATE USING (true);

CREATE POLICY "API can insert verification attempts" ON verification_attempts
    FOR INSERT WITH CHECK (true);

-- Create views for common queries
CREATE VIEW payment_summary AS
SELECT 
    id,
    txid,
    amount,
    status,
    customer_name,
    customer_phone,
    fraud_score,
    timestamp,
    created_at
FROM received_payments
ORDER BY created_at DESC;

CREATE VIEW daily_stats AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_payments,
    COUNT(CASE WHEN status = 'verified' THEN 1 END) as verified_payments,
    SUM(amount) as total_amount,
    AVG(fraud_score) as avg_fraud_score
FROM received_payments 
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Sample data for testing (remove in production)
INSERT INTO received_payments (
    sender_number, 
    sms_text, 
    amount, 
    txid, 
    parsed_data,
    status
) VALUES 
(
    '+250781234567',
    'MTN Mobile Money: You received RWF 50,000.00 from JOHN DOE (0781234567). Ref: MP240815123456',
    50000.00,
    'MP240815123456',
    '{"txid": "MP240815123456", "amount": 50000, "name": "JOHN DOE", "phone": "250781234567", "confidence": 0.95}',
    'unverified'
),
(
    '+250788987654',
    'Airtel Money: Transfer successful. Amount: 25000 RWF. TxnID: AM20240815001. From: ALICE UWIMANA (0788987654)',
    25000.00,
    'AM20240815001',
    '{"txid": "AM20240815001", "amount": 25000, "name": "ALICE UWIMANA", "phone": "250788987654", "confidence": 0.9}',
    'unverified'
);

-- Functions for common operations
CREATE OR REPLACE FUNCTION get_unverified_payments()
RETURNS TABLE (
    id UUID,
    txid VARCHAR(50),
    amount DECIMAL(12,2),
    sender_number VARCHAR(20),
    timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT rp.id, rp.txid, rp.amount, rp.sender_number, rp.timestamp
    FROM received_payments rp
    WHERE rp.status = 'unverified'
    ORDER BY rp.timestamp DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_payment_status(
    payment_id UUID,
    new_status VARCHAR(20),
    customer_name VARCHAR(100) DEFAULT NULL,
    customer_phone VARCHAR(20) DEFAULT NULL,
    fraud_score DECIMAL(3,2) DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE received_payments 
    SET 
        status = new_status,
        customer_name = COALESCE(update_payment_status.customer_name, received_payments.customer_name),
        customer_phone = COALESCE(update_payment_status.customer_phone, received_payments.customer_phone),
        fraud_score = COALESCE(update_payment_status.fraud_score, received_payments.fraud_score),
        updated_at = NOW()
    WHERE id = payment_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SETUP INSTRUCTIONS:
-- =============================================================================
-- 1. Copy this entire SQL script
-- 2. Go to your Supabase project dashboard
-- 3. Navigate to SQL Editor
-- 4. Paste and run this script
-- 5. Verify all tables and functions are created successfully
-- 6. Test with sample data or remove sample inserts for production
-- =============================================================================
