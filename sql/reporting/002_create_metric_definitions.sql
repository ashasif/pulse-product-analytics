CREATE TABLE IF NOT EXISTS reporting.metric_definitions (
    metric_key              text PRIMARY KEY,
    metric_name             text NOT NULL,
    metric_domain           text NOT NULL,
    metric_grain            text NOT NULL,
    metric_unit             text NOT NULL,
    support_status          text NOT NULL,
    definition              text NOT NULL,
    denominator_definition  text,
    caveat                  text,

    CONSTRAINT reporting_metric_definitions_support_chk
        CHECK (support_status IN ('supported', 'deferred', 'unsupported'))
);

COMMENT ON TABLE reporting.metric_definitions IS
    'Canonical Pulse reporting metric contracts. Unsupported or deferred metrics are recorded explicitly to prevent downstream invention of ambiguous definitions.';

INSERT INTO reporting.metric_definitions (
    metric_key,
    metric_name,
    metric_domain,
    metric_grain,
    metric_unit,
    support_status,
    definition,
    denominator_definition,
    caveat
)
VALUES
    (
        'installation_count',
        'Installations',
        'acquisition',
        'installation cohort',
        'count',
        'supported',
        'Count of analytics.dim_installation rows.',
        NULL,
        NULL
    ),
    (
        'signup_count',
        'Signups',
        'funnel',
        'user',
        'count',
        'supported',
        'Count of registered users in analytics.dim_user.',
        NULL,
        NULL
    ),
    (
        'install_to_signup_rate',
        'Install to Signup Rate',
        'funnel',
        'installation cohort',
        'rate',
        'supported',
        'Installations associated with at least one registered user divided by installations in the same installation cohort.',
        'Installation count for the cohort.',
        'Must use installation cohort grain rather than mixing signup occurrence dates with installation dates.'
    ),
    (
        'onboarding_start_rate',
        'Onboarding Start Rate',
        'funnel',
        'registered-user cohort',
        'rate',
        'supported',
        'Registered users with onboarding_started_at divided by registered users.',
        'Registered users in the cohort.',
        NULL
    ),
    (
        'onboarding_completion_rate',
        'Onboarding Completion Rate',
        'funnel',
        'registered-user cohort',
        'rate',
        'supported',
        'Registered users with onboarding_completed_at divided by registered users.',
        'Registered users in the cohort.',
        NULL
    ),
    (
        'registered_dau',
        'Registered Daily Active Users',
        'engagement',
        'calendar date',
        'count',
        'supported',
        'Distinct non-null user_key values with a session_started event on the date.',
        NULL,
        'Anonymous pre-signup sessions are deliberately excluded.'
    ),
    (
        'session_count',
        'Sessions Started',
        'engagement',
        'calendar date',
        'count',
        'supported',
        'Count of session_started product events.',
        NULL,
        NULL
    ),
    (
        'feature_use_event_count',
        'Feature Use Events',
        'engagement',
        'calendar date',
        'count',
        'supported',
        'Count of feature_used product events.',
        NULL,
        NULL
    ),
    (
        'paywall_view_count',
        'Paywall Views',
        'engagement',
        'calendar date',
        'count',
        'supported',
        'Count of paywall_viewed product events.',
        NULL,
        NULL
    ),
    (
        'trial_start_count',
        'Trial Starts',
        'subscription',
        'calendar date',
        'count',
        'supported',
        'Count of trial_started product events.',
        NULL,
        NULL
    ),
    (
        'paid_subscription_start_count',
        'Paid Subscription Starts',
        'subscription',
        'calendar date',
        'count',
        'supported',
        'Count of subscription_started product events.',
        NULL,
        NULL
    ),
    (
        'trial_to_paid_conversion_rate',
        'Trial to Paid Conversion Rate',
        'subscription',
        'trial cohort',
        'rate',
        'supported',
        'Trials that subsequently have subscription_started_at divided by mature trials.',
        'Trials mature enough to have reached their trial end before the reporting cutoff.',
        'Immature trials must not be included in the denominator.'
    ),
    (
        'successful_payment_revenue_gbp',
        'Successful Payment Revenue',
        'revenue',
        'payment attempt date',
        'GBP',
        'supported',
        'Sum of amount_gbp for subscription transactions where payment_status = succeeded.',
        NULL,
        'Represents successful billed cash collection, not accounting revenue recognition or net revenue.'
    ),
    (
        'payment_failure_rate',
        'Payment Failure Rate',
        'revenue',
        'payment attempt date',
        'rate',
        'supported',
        'Failed payment attempts divided by all payment attempts.',
        'All subscription transaction attempts.',
        NULL
    ),
    (
        'renewal_success_rate',
        'Renewal Success Rate',
        'subscription',
        'renewal attempt date',
        'rate',
        'supported',
        'Successful renewal transactions divided by all renewal transaction attempts.',
        'Transactions where transaction_type = renewal.',
        NULL
    ),
    (
        'paid_retention_d30',
        'Paid D30 Retention',
        'retention',
        'paid-subscription cohort',
        'rate',
        'supported',
        'Paid subscriptions still unexpired 30 days after subscription_started_at.',
        'Paid subscriptions mature enough to be observed for 30 days.',
        NULL
    ),
    (
        'paid_retention_d90',
        'Paid D90 Retention',
        'retention',
        'paid-subscription cohort',
        'rate',
        'supported',
        'Paid subscriptions still unexpired 90 days after subscription_started_at.',
        'Paid subscriptions mature enough to be observed for 90 days.',
        NULL
    ),
    (
        'paid_retention_d180',
        'Paid D180 Retention',
        'retention',
        'paid-subscription cohort',
        'rate',
        'supported',
        'Paid subscriptions still unexpired 180 days after subscription_started_at.',
        'Paid subscriptions mature enough to be observed for 180 days.',
        NULL
    ),
    (
        'paid_retention_d365',
        'Paid D365 Retention',
        'retention',
        'paid-subscription cohort',
        'rate',
        'supported',
        'Paid subscriptions still unexpired 365 days after subscription_started_at.',
        'Paid subscriptions mature enough to be observed for 365 days.',
        NULL
    ),
    (
        'marketing_spend_gbp',
        'Marketing Spend',
        'acquisition',
        'marketing period and acquisition channel',
        'GBP',
        'supported',
        'Sum of fact_marketing_spend.spend.',
        NULL,
        'Source currency is GBP in the current approved snapshot.'
    ),
    (
        'marketing_ctr',
        'Marketing Click Through Rate',
        'acquisition',
        'marketing period and acquisition channel',
        'rate',
        'supported',
        'Clicks divided by impressions when impressions are present and greater than zero.',
        'Marketing impressions.',
        NULL
    ),
    (
        'marketing_cpc_gbp',
        'Marketing Cost Per Click',
        'acquisition',
        'marketing period and acquisition channel',
        'GBP',
        'supported',
        'Marketing spend divided by clicks when clicks are present and greater than zero.',
        'Marketing clicks.',
        NULL
    ),
    (
        'cost_per_install_gbp',
        'Cost Per Install',
        'acquisition',
        'marketing period and acquisition channel',
        'GBP',
        'supported',
        'Channel marketing spend divided by installations acquired in the corresponding acquisition period.',
        'Installations for the same acquisition channel and acquisition period.',
        'This is channel-level acquisition efficiency, not campaign-level CAC.'
    ),
    (
        'average_session_duration_seconds',
        'Average Session Duration',
        'engagement',
        'session',
        'seconds',
        'unsupported',
        'Not defined.',
        NULL,
        'No session-end timestamp or equivalent session duration field exists in the analytics contract.'
    ),
    (
        'recognized_revenue_gbp',
        'Recognized Revenue',
        'revenue',
        'accounting period',
        'GBP',
        'unsupported',
        'Not defined.',
        NULL,
        'The warehouse contains successful billing transactions but no accounting revenue-recognition schedule.'
    ),
    (
        'net_revenue_gbp',
        'Net Revenue',
        'revenue',
        'payment period',
        'GBP',
        'unsupported',
        'Not defined.',
        NULL,
        'Refunds, taxes, payment processor fees and other net-revenue adjustments are not represented.'
    ),
    (
        'campaign_attributed_cac_gbp',
        'Campaign Attributed CAC',
        'acquisition',
        'campaign',
        'GBP',
        'unsupported',
        'Not defined.',
        NULL,
        'Installation records contain acquisition_channel but no campaign identifier linking individual acquisitions to marketing campaigns.'
    ),
    (
        'customer_ltv_gbp',
        'Customer Lifetime Value',
        'revenue',
        'customer',
        'GBP',
        'deferred',
        'Observed customer revenue can be measured, but complete lifetime value is not canonicalized.',
        NULL,
        'Recent customer lifetimes are right-censored at the reporting snapshot.'
    ),
    (
        'activation_48h',
        'Activation Within 48 Hours',
        'experiment',
        'assigned user',
        'rate',
        'deferred',
        'Not yet canonicalized.',
        NULL,
        'Experiment metadata references activation_48h but does not define the exact activation business rule.'
    ),
    (
        'd7_return_rate',
        'D7 Return Rate',
        'experiment',
        'assigned user',
        'rate',
        'deferred',
        'Not yet canonicalized.',
        NULL,
        'The metric label alone does not establish whether D7 means exact day seven, a window, or another return-session convention.'
    )
ON CONFLICT (metric_key) DO UPDATE
SET
    metric_name            = EXCLUDED.metric_name,
    metric_domain          = EXCLUDED.metric_domain,
    metric_grain           = EXCLUDED.metric_grain,
    metric_unit            = EXCLUDED.metric_unit,
    support_status         = EXCLUDED.support_status,
    definition             = EXCLUDED.definition,
    denominator_definition = EXCLUDED.denominator_definition,
    caveat                 = EXCLUDED.caveat;
