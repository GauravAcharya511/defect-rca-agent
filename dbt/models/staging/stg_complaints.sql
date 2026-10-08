-- One row per complaint x component x vehicle, typed and cleaned.
with src as (
    select * from {{ source('bronze', 'nhtsa_complaints_flat') }}
)
select
    odi_number,
    make,
    model,
    model_year,
    component,
    btrim(split_part(component, ':', 1))                         as component_group,
    public.try_date(payload->>'FAILDATE', 'YYYYMMDD')            as fail_date,
    public.try_date(payload->>'LDATE', 'YYYYMMDD')               as received_date,
    coalesce(payload->>'CRASH', 'N') = 'Y'                       as is_crash,
    coalesce(payload->>'FIRE', 'N') = 'Y'                        as is_fire,
    coalesce(nullif(payload->>'INJURED', '')::int, 0)            as injuries,
    coalesce(nullif(payload->>'DEATHS', '')::int, 0)             as deaths,
    case when payload->>'MILES' ~ '^\d+$' then (payload->>'MILES')::int end as miles,
    payload->>'STATE'                                            as state,
    payload->>'CDESCR'                                           as description,
    source_file
from src
