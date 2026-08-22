select
    created_date as metric_date,
    community_district,
    borough,
    agency,
    problem,
    channel,
    count(*) as request_count,
    count(*) filter (where is_closed) as closed_count,
    median(resolution_days) filter (where is_closed) as median_resolution_days
from {{ ref('fct_requests') }}
group by all

