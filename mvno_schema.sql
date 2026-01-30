-- MVNO Usage Prediction System - Database Schema
-- PostgreSQL + TimescaleDB
-- Created: 2026-01-30

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =====================================================
-- CORE SUBSCRIBER TABLES
-- =====================================================

-- Subscribers master table
CREATE TABLE subscribers (
    subscriber_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) UNIQUE NOT NULL,
    imsi VARCHAR(17),
    tenant_id BIGINT NOT NULL,
    billing_code VARCHAR(20),
    bundle_id VARCHAR(20),
    activation_date TIMESTAMPTZ,
    deactivation_date TIMESTAMPTZ,
    current_status VARCHAR(20) CHECK (current_status IN ('ACTIVE', 'SUSPENDED', 'DEACTIVATED')),
    iccid VARCHAR(22),
    zipcode VARCHAR(5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subscribers_msisdn ON subscribers(msisdn);
CREATE INDEX idx_subscribers_status ON subscribers(current_status);
CREATE INDEX idx_subscribers_bundle ON subscribers(bundle_id);

-- =====================================================
-- DAILY SUBSCRIBER REPORTS (DSR)
-- =====================================================

-- Daily subscriber snapshots
CREATE TABLE daily_subscriber_reports (
    id BIGSERIAL,
    usage_date DATE NOT NULL,
    msisdn VARCHAR(50) NOT NULL,
    imsi VARCHAR(17),
    tenant_id BIGINT,
    billing_code VARCHAR(20),
    active_status SMALLINT,
    suspend_status SMALLINT,
    voice_minutes DECIMAL(10,2),
    sms_units DECIMAL(10,2),
    data_bytes DECIMAL(18,3),
    flag VARCHAR(20),
    subscriber_state VARCHAR(20),
    activation_date TIMESTAMPTZ,
    suspend_date TIMESTAMPTZ,
    deactivation_date TIMESTAMPTZ,
    bundle_id VARCHAR(20),
    expiration_date DATE,
    iccid VARCHAR(22),
    zipcode VARCHAR(5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (usage_date, msisdn)
);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('daily_subscriber_reports', 'usage_date', 
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_dsr_msisdn ON daily_subscriber_reports(msisdn);
CREATE INDEX idx_dsr_bundle ON daily_subscriber_reports(bundle_id);
CREATE INDEX idx_dsr_state ON daily_subscriber_reports(subscriber_state);

-- =====================================================
-- CALL DETAIL RECORDS (CDR)
-- =====================================================

-- Voice CDRs
CREATE TABLE cdr_voice (
    id BIGSERIAL,
    effective_date TIMESTAMPTZ NOT NULL,
    tenant_id BIGINT,
    msisdn VARCHAR(50) NOT NULL,
    subscriber_id BIGINT,
    usage_type VARCHAR(20),
    originating_network_type VARCHAR(30),
    carrier_effective_date TIMESTAMPTZ,
    other_party_number VARCHAR(80),
    account_number VARCHAR(20),
    sequence_number VARCHAR(9),
    imsi VARCHAR(17),
    channel_seizure_dt VARCHAR(14),
    switch_id VARCHAR(6),
    imei VARCHAR(19),
    home_sid VARCHAR(5),
    serve_sid VARCHAR(5),
    cell_identity VARCHAR(13),
    call_to_place VARCHAR(30),
    call_to_region VARCHAR(30),
    outgoing_trunk_id VARCHAR(16),
    incoming_trunk_id VARCHAR(16),
    duration_minutes INTEGER,
    duration_seconds INTEGER,
    toll_charge_code VARCHAR(2),
    on_network_flag VARCHAR(1),
    translated_number VARCHAR(40),
    plmn_code VARCHAR(6),
    country_name VARCHAR(24),
    gmt_offset VARCHAR(7),
    subscriber_type VARCHAR(7),
    technology_used VARCHAR(8),
    package_name VARCHAR(83),
    supp_serv_code VARCHAR(40),
    billing_code VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (effective_date, id)
);

-- Convert to hypertable
SELECT create_hypertable('cdr_voice', 'effective_date',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_cdr_voice_msisdn ON cdr_voice(msisdn);
CREATE INDEX idx_cdr_voice_usage_type ON cdr_voice(usage_type);

-- SMS CDRs
CREATE TABLE cdr_sms (
    id BIGSERIAL,
    effective_date TIMESTAMPTZ NOT NULL,
    tenant_id BIGINT,
    msisdn VARCHAR(50) NOT NULL,
    subscriber_id BIGINT,
    usage_type VARCHAR(20),
    originating_network_type VARCHAR(30),
    carrier_effective_date TIMESTAMPTZ,
    other_party_number VARCHAR(80),
    account_number VARCHAR(20),
    sequence_number VARCHAR(9),
    imsi VARCHAR(17),
    channel_seizure_dt VARCHAR(14),
    switch_id VARCHAR(6),
    imei VARCHAR(19),
    home_sid VARCHAR(5),
    serve_sid VARCHAR(5),
    cell_identity VARCHAR(13),
    call_to_place VARCHAR(30),
    call_to_region VARCHAR(30),
    outgoing_trunk_id VARCHAR(16),
    incoming_trunk_id VARCHAR(16),
    message_count INTEGER,
    toll_charge_code VARCHAR(2),
    on_network_flag VARCHAR(1),
    translated_number VARCHAR(40),
    plmn_code VARCHAR(6),
    country_name VARCHAR(24),
    gmt_offset VARCHAR(7),
    subscriber_type VARCHAR(7),
    technology_used VARCHAR(8),
    package_name VARCHAR(83),
    supp_serv_code VARCHAR(40),
    billing_code VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (effective_date, id)
);

SELECT create_hypertable('cdr_sms', 'effective_date',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_cdr_sms_msisdn ON cdr_sms(msisdn);
CREATE INDEX idx_cdr_sms_usage_type ON cdr_sms(usage_type);

-- Data CDRs
CREATE TABLE cdr_data (
    id BIGSERIAL,
    effective_date TIMESTAMPTZ NOT NULL,
    tenant_id BIGINT,
    msisdn VARCHAR(50) NOT NULL,
    subscriber_id BIGINT,
    usage_type VARCHAR(20),
    originating_network_type VARCHAR(30),
    carrier_effective_date TIMESTAMPTZ,
    account_number VARCHAR(20),
    sequence_number VARCHAR(9),
    imsi VARCHAR(17),
    record_start_time VARCHAR(14),
    access_point_name VARCHAR(50),
    imei VARCHAR(19),
    home_sid VARCHAR(5),
    serve_sid VARCHAR(5),
    served_pdp_address VARCHAR(40),
    served_pdp_address_v6 VARCHAR(50),
    cell_identity VARCHAR(50),
    location_area_code VARCHAR(6),
    total_volume_bytes DECIMAL(18,3),
    duration_seconds INTEGER,
    data_description VARCHAR(25),
    data_charge_code VARCHAR(2),
    on_network_flag VARCHAR(1),
    mms_type_indicator VARCHAR(2),
    called_number_url VARCHAR(15),
    uplink_volume_bytes DECIMAL(18,3),
    downlink_volume_bytes DECIMAL(18,3),
    plmn_code VARCHAR(6),
    country_name VARCHAR(24),
    ggsn_address VARCHAR(15),
    charging_id VARCHAR(10),
    cause_for_close VARCHAR(2),
    record_entity VARCHAR(8),
    utc_offset VARCHAR(7),
    subscriber_type VARCHAR(7),
    technology_used VARCHAR(8),
    package_name VARCHAR(83),
    in_rating_group VARCHAR(5),
    billing_code VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (effective_date, id)
);

SELECT create_hypertable('cdr_data', 'effective_date',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_cdr_data_msisdn ON cdr_data(msisdn);
CREATE INDEX idx_cdr_data_usage_type ON cdr_data(usage_type);

-- =====================================================
-- USAGE AGGREGATIONS (for faster queries)
-- =====================================================

-- Daily usage aggregates per subscriber
CREATE TABLE usage_daily_agg (
    usage_date DATE NOT NULL,
    msisdn VARCHAR(50) NOT NULL,
    voice_minutes DECIMAL(10,2) DEFAULT 0,
    sms_count INTEGER DEFAULT 0,
    data_bytes BIGINT DEFAULT 0,
    voice_events INTEGER DEFAULT 0,
    sms_events INTEGER DEFAULT 0,
    data_sessions INTEGER DEFAULT 0,
    roaming_voice_minutes DECIMAL(10,2) DEFAULT 0,
    roaming_data_bytes BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (usage_date, msisdn)
);

SELECT create_hypertable('usage_daily_agg', 'usage_date',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_usage_daily_msisdn ON usage_daily_agg(msisdn);

-- Monthly usage aggregates (running totals)
CREATE TABLE usage_monthly_agg (
    billing_month DATE NOT NULL, -- First day of billing month
    msisdn VARCHAR(50) NOT NULL,
    days_in_cycle INTEGER DEFAULT 0,
    voice_minutes DECIMAL(10,2) DEFAULT 0,
    sms_count INTEGER DEFAULT 0,
    data_bytes BIGINT DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (billing_month, msisdn)
);

CREATE INDEX idx_usage_monthly_msisdn ON usage_monthly_agg(msisdn);

-- =====================================================
-- PREDICTION MODELS
-- =====================================================

-- Real-time usage predictions (15-min to 1-hour forecasts)
CREATE TABLE predictions_realtime (
    prediction_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) NOT NULL,
    prediction_timestamp TIMESTAMPTZ NOT NULL,
    forecast_horizon_minutes INTEGER, -- 15, 30, 60
    predicted_data_mb DECIMAL(10,2),
    predicted_voice_minutes DECIMAL(10,2),
    predicted_sms_count INTEGER,
    confidence_lower DECIMAL(10,2),
    confidence_upper DECIMAL(10,2),
    model_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pred_realtime_msisdn ON predictions_realtime(msisdn);
CREATE INDEX idx_pred_realtime_timestamp ON predictions_realtime(prediction_timestamp DESC);

-- Current month predictions (updated daily)
CREATE TABLE predictions_current_month (
    prediction_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) NOT NULL,
    billing_month DATE NOT NULL,
    prediction_date DATE NOT NULL,
    predicted_voice_minutes DECIMAL(10,2),
    predicted_sms_count INTEGER,
    predicted_data_bytes BIGINT,
    predicted_data_gb DECIMAL(10,2),
    confidence_lower_gb DECIMAL(10,2),
    confidence_upper_gb DECIMAL(10,2),
    days_remaining INTEGER,
    current_usage_gb DECIMAL(10,2),
    model_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(msisdn, billing_month, prediction_date)
);

CREATE INDEX idx_pred_current_msisdn ON predictions_current_month(msisdn);
CREATE INDEX idx_pred_current_date ON predictions_current_month(prediction_date DESC);

-- Next month predictions
CREATE TABLE predictions_next_month (
    prediction_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) NOT NULL,
    current_month DATE NOT NULL,
    next_month DATE NOT NULL,
    predicted_voice_minutes DECIMAL(10,2),
    predicted_sms_count INTEGER,
    predicted_data_bytes BIGINT,
    predicted_data_gb DECIMAL(10,2),
    confidence_lower_gb DECIMAL(10,2),
    confidence_upper_gb DECIMAL(10,2),
    model_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(msisdn, next_month)
);

CREATE INDEX idx_pred_next_msisdn ON predictions_next_month(msisdn);
CREATE INDEX idx_pred_next_month ON predictions_next_month(next_month);

-- =====================================================
-- POOL OPTIMIZATION
-- =====================================================

-- Data pool tiers configuration
CREATE TABLE pool_tiers (
    tier_id SERIAL PRIMARY KEY,
    tier_name VARCHAR(50) NOT NULL,
    data_cap_gb DECIMAL(10,2) NOT NULL,
    cost_per_subscriber DECIMAL(10,2) NOT NULL,
    overage_cost_per_gb DECIMAL(10,2),
    min_subscribers INTEGER,
    max_subscribers INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pool assignments (current and historical)
CREATE TABLE pool_assignments (
    assignment_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) NOT NULL,
    tier_id INTEGER REFERENCES pool_tiers(tier_id),
    billing_month DATE NOT NULL,
    assigned_date TIMESTAMPTZ DEFAULT NOW(),
    reason VARCHAR(100), -- 'initial', 'usage_prediction', 'cost_optimization', 'manual'
    previous_tier_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pool_assignments_msisdn ON pool_assignments(msisdn);
CREATE INDEX idx_pool_assignments_month ON pool_assignments(billing_month);
CREATE INDEX idx_pool_assignments_tier ON pool_assignments(tier_id);

-- Pool optimization results (daily calculations)
CREATE TABLE pool_optimization_log (
    log_id BIGSERIAL PRIMARY KEY,
    calculation_date DATE NOT NULL,
    billing_month DATE NOT NULL,
    total_subscribers INTEGER,
    tier_distribution JSONB, -- {"tier_1": 1500, "tier_2": 800, "tier_3": 200}
    total_cost DECIMAL(12,2),
    potential_cost_without_optimization DECIMAL(12,2),
    cost_savings DECIMAL(12,2),
    moved_subscribers INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pool_opt_date ON pool_optimization_log(calculation_date DESC);

-- =====================================================
-- DONATION SYSTEM
-- =====================================================

-- Donation thresholds (safe amounts users can donate)
CREATE TABLE donation_thresholds (
    threshold_id BIGSERIAL PRIMARY KEY,
    msisdn VARCHAR(50) NOT NULL,
    billing_month DATE NOT NULL,
    calculation_date DATE NOT NULL,
    allocated_data_gb DECIMAL(10,2),
    predicted_usage_gb DECIMAL(10,2),
    confidence_buffer_gb DECIMAL(10,2),
    safe_donation_amount_gb DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(msisdn, billing_month, calculation_date)
);

CREATE INDEX idx_donation_msisdn ON donation_thresholds(msisdn);
CREATE INDEX idx_donation_month ON donation_thresholds(billing_month);
CREATE INDEX idx_donation_active ON donation_thresholds(is_active);

-- Actual donations made
CREATE TABLE donations (
    donation_id BIGSERIAL PRIMARY KEY,
    donor_msisdn VARCHAR(50) NOT NULL,
    recipient_msisdn VARCHAR(50),
    donation_amount_gb DECIMAL(10,2) NOT NULL,
    donation_date TIMESTAMPTZ DEFAULT NOW(),
    billing_month DATE NOT NULL,
    status VARCHAR(20) CHECK (status IN ('pending', 'completed', 'revoked')),
    reward_points INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_donations_donor ON donations(donor_msisdn);
CREATE INDEX idx_donations_recipient ON donations(recipient_msisdn);
CREATE INDEX idx_donations_month ON donations(billing_month);

-- =====================================================
-- MONITORING & LOGGING
-- =====================================================

-- ETL job runs
CREATE TABLE etl_runs (
    run_id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    status VARCHAR(20) CHECK (status IN ('running', 'completed', 'failed')),
    records_processed INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_etl_runs_job ON etl_runs(job_name);
CREATE INDEX idx_etl_runs_status ON etl_runs(status);
CREATE INDEX idx_etl_runs_time ON etl_runs(start_time DESC);

-- Model performance metrics
CREATE TABLE model_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    evaluation_date DATE NOT NULL,
    metric_type VARCHAR(50), -- 'RMSE', 'MAE', 'R2', etc.
    metric_value DECIMAL(10,4),
    dataset_type VARCHAR(20), -- 'training', 'validation', 'test'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_model_metrics_name ON model_metrics(model_name);
CREATE INDEX idx_model_metrics_date ON model_metrics(evaluation_date DESC);

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- Current subscriber status with latest predictions
CREATE OR REPLACE VIEW v_subscriber_dashboard AS
SELECT 
    s.msisdn,
    s.bundle_id,
    s.current_status,
    uma.data_bytes / 1073741824.0 AS current_month_usage_gb,
    pcm.predicted_data_gb,
    pcm.confidence_lower_gb,
    pcm.confidence_upper_gb,
    dt.safe_donation_amount_gb,
    pa.tier_id,
    pt.tier_name,
    pt.data_cap_gb
FROM subscribers s
LEFT JOIN usage_monthly_agg uma ON s.msisdn = uma.msisdn 
    AND uma.billing_month = DATE_TRUNC('month', CURRENT_DATE)
LEFT JOIN LATERAL (
    SELECT * FROM predictions_current_month 
    WHERE msisdn = s.msisdn 
    AND billing_month = DATE_TRUNC('month', CURRENT_DATE)
    ORDER BY prediction_date DESC LIMIT 1
) pcm ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM donation_thresholds 
    WHERE msisdn = s.msisdn 
    AND billing_month = DATE_TRUNC('month', CURRENT_DATE)
    AND is_active = TRUE
    ORDER BY calculation_date DESC LIMIT 1
) dt ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM pool_assignments 
    WHERE msisdn = s.msisdn 
    AND billing_month = DATE_TRUNC('month', CURRENT_DATE)
    ORDER BY assigned_date DESC LIMIT 1
) pa ON TRUE
LEFT JOIN pool_tiers pt ON pa.tier_id = pt.tier_id;

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to calculate month-to-date usage
CREATE OR REPLACE FUNCTION get_mtd_usage(p_msisdn VARCHAR, p_date DATE DEFAULT CURRENT_DATE)
RETURNS TABLE(voice_minutes DECIMAL, sms_count BIGINT, data_gb DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        SUM(voice_minutes)::DECIMAL(10,2),
        SUM(sms_count)::BIGINT,
        (SUM(data_bytes) / 1073741824.0)::DECIMAL(10,2)
    FROM usage_daily_agg
    WHERE msisdn = p_msisdn
    AND usage_date >= DATE_TRUNC('month', p_date)
    AND usage_date <= p_date;
END;
$$ LANGUAGE plpgsql;

-- Function to update monthly aggregates
CREATE OR REPLACE FUNCTION update_monthly_aggregates()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO usage_monthly_agg (
        billing_month, 
        msisdn, 
        days_in_cycle,
        voice_minutes, 
        sms_count, 
        data_bytes,
        last_updated
    )
    VALUES (
        DATE_TRUNC('month', NEW.usage_date),
        NEW.msisdn,
        1,
        NEW.voice_minutes,
        NEW.sms_count,
        NEW.data_bytes,
        NOW()
    )
    ON CONFLICT (billing_month, msisdn) 
    DO UPDATE SET
        days_in_cycle = usage_monthly_agg.days_in_cycle + 1,
        voice_minutes = usage_monthly_agg.voice_minutes + NEW.voice_minutes,
        sms_count = usage_monthly_agg.sms_count + NEW.sms_count,
        data_bytes = usage_monthly_agg.data_bytes + NEW.data_bytes,
        last_updated = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update monthly aggregates
CREATE TRIGGER trigger_update_monthly_agg
    AFTER INSERT OR UPDATE ON usage_daily_agg
    FOR EACH ROW
    EXECUTE FUNCTION update_monthly_aggregates();

-- =====================================================
-- SAMPLE DATA INSERTS (for testing)
-- =====================================================

-- Insert sample pool tiers
INSERT INTO pool_tiers (tier_name, data_cap_gb, cost_per_subscriber, overage_cost_per_gb, min_subscribers, max_subscribers) VALUES
('Tier 1 - Basic', 5.0, 15.00, 10.00, 0, 10000),
('Tier 2 - Standard', 10.0, 25.00, 8.00, 0, 20000),
('Tier 3 - Premium', 20.0, 40.00, 6.00, 0, 30000);

-- Comments for documentation
COMMENT ON TABLE subscribers IS 'Master table of all MVNO subscribers';
COMMENT ON TABLE daily_subscriber_reports IS 'Daily snapshots from DSR files (updated every 15 mins)';
COMMENT ON TABLE cdr_voice IS 'Voice call detail records';
COMMENT ON TABLE cdr_sms IS 'SMS call detail records';
COMMENT ON TABLE cdr_data IS 'Data usage call detail records';
COMMENT ON TABLE usage_daily_agg IS 'Pre-aggregated daily usage for fast queries';
COMMENT ON TABLE usage_monthly_agg IS 'Running monthly usage totals';
COMMENT ON TABLE predictions_current_month IS 'End-of-month usage predictions updated daily';
COMMENT ON TABLE predictions_next_month IS 'Next month usage predictions';
COMMENT ON TABLE pool_assignments IS 'Historical record of pool tier assignments';
COMMENT ON TABLE donation_thresholds IS 'Safe donation amounts calculated daily';