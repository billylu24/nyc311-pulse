select
    count(*) as rows_checked,
    count(distinct request_id) as unique_request_ids,
    count(*) filter (where community_district = 'UNSPECIFIED') as unspecified_district_rows,
    count(*) filter (where closed_at_local < created_at_local) as invalid_date_rows,
    count(*) filter (where problem is null or problem = '') as missing_problem_rows
from {{ ref('fct_requests') }}

