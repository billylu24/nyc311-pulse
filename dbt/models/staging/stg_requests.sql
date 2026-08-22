with source as (
    select * from read_json_auto('{{ var("raw_glob") }}', format = 'newline_delimited')
)
select
    cast(unique_key as varchar) as request_id,
    cast(created_date as timestamp) as created_at_local,
    cast(closed_date as timestamp) as closed_at_local,
    upper(trim(agency)) as agency,
    trim(agency_name) as agency_name,
    trim(complaint_type) as problem,
    nullif(trim(descriptor), '') as problem_detail,
    upper(trim(status)) as status,
    upper(trim(borough)) as borough,
    upper(trim(community_board)) as community_district,
    upper(trim(open_data_channel_type)) as channel
from source

