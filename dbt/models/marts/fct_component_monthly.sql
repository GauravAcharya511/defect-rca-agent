-- Complaint volume per vehicle x component group x month.
-- Month = failure month when known, else received month.
select
    make,
    model,
    model_year,
    component_group,
    date_trunc('month', coalesce(fail_date, received_date))::date as month,
    count(distinct odi_number)                                    as complaints,
    count(distinct odi_number) filter (where is_crash)            as crash_complaints,
    count(distinct odi_number) filter (where is_fire)             as fire_complaints,
    sum(injuries)                                                 as injuries
from {{ ref('stg_complaints') }}
where coalesce(fail_date, received_date) is not null
group by 1, 2, 3, 4, 5
