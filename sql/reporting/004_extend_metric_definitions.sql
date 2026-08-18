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
        'experiment_exposure_rate',
        'Experiment Exposure Rate',
        'experiment',
        'experiment variant',
        'rate',
        'supported',
        'Assigned users with a non-null exposed_at divided by assigned users.',
        'Experiment assignments.',
        NULL
    ),
    (
        'onboarding_completion_48h',
        'Onboarding Completion Within 48 Hours',
        'experiment',
        'assigned user',
        'rate',
        'supported',
        'Assigned users whose onboarding_completed_at occurs within 48 hours after assignment.',
        'Assigned users.',
        'Most directly applicable to experiments whose assignment occurs at signup or onboarding entry.'
    ),
    (
        'trial_start_conversion_7d',
        'Trial Start Conversion Within 7 Days',
        'experiment',
        'assigned user',
        'rate',
        'supported',
        'Assigned users with at least one trial_started event within seven days after assignment.',
        'Assigned users.',
        NULL
    ),
    (
        'paid_conversion_14d',
        'Paid Conversion Within 14 Days',
        'experiment',
        'assigned user',
        'rate',
        'supported',
        'Assigned users with at least one subscription_started event within fourteen days after assignment.',
        'Assigned users.',
        NULL
    ),
    (
        'revenue_per_assigned_user_30d',
        'Successful Revenue per Assigned User Within 30 Days',
        'experiment',
        'experiment variant',
        'GBP',
        'supported',
        'Successful payment revenue within thirty days after assignment divided by assigned users.',
        'Assigned users.',
        'Represents successful payment collection, not accounting recognised revenue.'
    ),
    (
        'cancellation_or_expiry_30d',
        'Cancellation or Expiry Within 30 Days',
        'experiment',
        'assigned user',
        'rate',
        'supported',
        'Assigned users with a cancellation_requested or subscription_expired event within thirty days after assignment.',
        'Assigned users.',
        NULL
    ),
    (
        'overall_feature_use_7d',
        'Any Feature Use Within 7 Days',
        'experiment',
        'assigned user',
        'rate',
        'supported',
        'Assigned users with at least one feature_used event within seven days after assignment.',
        'Assigned users.',
        'This is overall feature use and does not identify a specific feature.'
    ),
    (
        'ai_assistant_use_7d',
        'AI Assistant Use Within 7 Days',
        'experiment',
        'assigned user',
        'rate',
        'deferred',
        'Not yet canonicalized.',
        NULL,
        'The experiment contract names this metric, but the exact feature_name value defining AI Assistant use has not yet been promoted into a canonical semantic rule.'
    ),
    (
        'return_session_7d',
        'Return Session Within 7 Days',
        'experiment',
        'assigned user',
        'rate',
        'deferred',
        'Not yet canonicalized.',
        NULL,
        'A precise return-session rule must distinguish the qualifying return from the triggering or assignment session.'
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