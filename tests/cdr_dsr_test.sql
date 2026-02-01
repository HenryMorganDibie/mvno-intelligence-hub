-- Check if DSR and CDR data are both present
SELECT 'DSR Records' as type, COUNT(*) FROM daily_subscriber_reports
UNION ALL
SELECT 'Voice Records' as type, COUNT(*) FROM cdr_voice
UNION ALL
SELECT 'Data Records' as type, COUNT(*) FROM cdr_data
UNION ALL
SELECT 'SMS Records' as type, COUNT(*) FROM cdr_sms;