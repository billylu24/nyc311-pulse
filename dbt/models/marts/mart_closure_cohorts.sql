select
    date_trunc('week', created_date) as cohort_week,
    community_district,
    problem,
    count(*) as requests,
    count(*) filter (where is_closed and resolution_days <= 7) as closed_within_7_days,
    count(*) filter (where not is_closed) as right_censored_requests
from {{ ref('fct_requests') }}
group by all

