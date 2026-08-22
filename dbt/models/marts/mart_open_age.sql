select
    community_district,
    borough,
    agency,
    problem,
    count(*) filter (where not is_closed) as unresolved_requests,
    count(*) filter (
        where not is_closed
        and created_at_local <= timestamp '2026-08-21 00:00:00' - interval 30 day
    ) as aged_30d_requests
from {{ ref('fct_requests') }}
group by all

