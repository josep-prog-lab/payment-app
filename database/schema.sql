-- Smart Payment Verification System - Supabase Database Schema
-- This schema supports MoMo payment verification with ML-powered fraud detection

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Companies/Businesses table
CREATE TABLE companies (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255),
    api_key VARCHAR(255) UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
    webhook_secret VARCHAR(255) NOT NULL DEFAULT encode(gen_random_bytes(16), 'hex'),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- SMS Messages received from forwarder app
CREATE TABLE received_payments (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    sender_number VARCHAR(20) NOT NULL,
    sms_text TEXT NOT NULL,
    amount DECIMAL(15,2),
    txid VARCHAR(50),
    sender_name VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE,
    parsed_data JSONB DEFAULT '{}',
    parsing_confidence DECIMAL(3,2) DEFAULT 0.0,
    status VARCHAR(20) DEFAULT 'unverified' CHECK (status IN ('unverified', 'verified', 'disputed', 'expired')),
    fraud_score DECIMAL(3,2) DEFAULT 0.0,
    ml_features JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Customer payment verification requests
CREATE TABLE payment_verifications (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    payment_id UUID REFERENCES received_payments(id) ON DELETE SET NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    submitted_txid VARCHAR(50) NOT NULL,
    submitted_amount DECIMAL(15,2),
    verification_status VARCHAR(20) DEFAULT 'pending' CHECK (
        verification_status IN ('pending', 'verified', 'failed', 'suspicious', 'manual_review')
    ),
    match_confidence DECIMAL(3,2) DEFAULT 0.0,
    fraud_risk DECIMAL(3,2) DEFAULT 0.0,
    verification_details JSONB DEFAULT '{}',
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fraud detection logs
CREATE TABLE fraud_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    verification_id UUID REFERENCES payment_verifications(id) ON DELETE CASCADE,
    fraud_type VARCHAR(50) NOT NULL,
    risk_score DECIMAL(3,2) NOT NULL,
    details JSONB DEFAULT '{}',
    ml_model_version VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ML Model training data
CREATE TABLE training_data (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    sms_text TEXT NOT NULL,
    parsed_amount DECIMAL(15,2),
    parsed_txid VARCHAR(50),
    parsed_name VARCHAR(255),
    parsed_phone VARCHAR(20),
    is_valid_parse BOOLEAN DEFAULT true,
    fraud_label BOOLEAN DEFAULT false,
    features JSONB DEFAULT '{}',
    model_version VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System analytics and metrics
CREATE TABLE analytics (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4),
    metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API usage logs for monitoring
CREATE TABLE api_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    request_data JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_received_payments_company_txid ON received_payments(company_id, txid);
CREATE INDEX idx_received_payments_status ON received_payments(status);
CREATE INDEX idx_received_payments_created_at ON received_payments(created_at);
CREATE INDEX idx_payment_verifications_company_status ON payment_verifications(company_id, verification_status);
CREATE INDEX idx_payment_verifications_txid ON payment_verifications(submitted_txid);
CREATE INDEX idx_fraud_logs_verification_id ON fraud_logs(verification_id);
CREATE INDEX idx_analytics_company_metric ON analytics(company_id, metric_name);
CREATE INDEX idx_api_logs_company_created ON api_logs(company_id, created_at);

-- Row Level Security (RLS) policies
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE received_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_logs ENABLE ROW LEVEL SECURITY;

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_received_payments_updated_at BEFORE UPDATE ON received_payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payment_verifications_updated_at BEFORE UPDATE ON payment_verifications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default company for testing
INSERT INTO companies (name, phone_number, email) 
VALUES ('Test Business', '+250788123456', 'test@business.rw')
ON CONFLICT (phone_number) DO NOTHING;
