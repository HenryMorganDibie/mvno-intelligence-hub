SELECT 
    COUNT(pa.msisdn) as total_subscribers,
    SUM(pt.cost_per_subscriber) as optimized_monthly_cost,
    SUM(58.00) as baseline_max_cost, -- Comparing against the 40GB Max Tier
    SUM(58.00 - pt.cost_per_subscriber) as total_projected_savings,
    ROUND(AVG(p.predicted_data_gb)::numeric, 2) as avg_forecasted_usage_gb
FROM pool_assignments pa
JOIN pool_tiers pt ON pa.tier_id = pt.tier_id
JOIN (
    -- Subquery to get the latest prediction for each msisdn
    SELECT DISTINCT ON (msisdn) msisdn, predicted_data_gb 
    FROM predictions_current_month 
    ORDER BY msisdn, prediction_date DESC
) p ON pa.msisdn = p.msisdn
WHERE pa.billing_month = '2026-01-21';