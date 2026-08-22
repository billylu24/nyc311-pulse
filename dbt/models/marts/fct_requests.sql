select
    request_id,
    created_at_local,
    closed_at_local,
    cast(created_at_local as date) as created_date,
    cast(closed_at_local as date) as closed_date,
    agency,
    agency_name,
    problem,
    problem_detail,
    status,
    borough,
    community_district,
    channel,
    closed_at_local is not null as is_closed,
    case when closed_at_local is not null
        then date_diff('minute', created_at_local, closed_at_local) / 1440.0
    end as resolution_days
from {{ ref('stg_requests') }}

