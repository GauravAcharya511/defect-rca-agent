-- One row per recall campaign x vehicle. ReportReceivedDate arrives as DD/MM/YYYY.
with src as (
    select * from {{ source('bronze', 'nhtsa_recalls_raw') }}
)
select
    campaign_number,
    make,
    model,
    model_year,
    payload->>'Component'                                        as component,
    btrim(split_part(payload->>'Component', ':', 1))             as component_group,
    public.try_date(payload->>'ReportReceivedDate', 'DD/MM/YYYY') as report_received_date,
    coalesce((payload->>'overTheAirUpdate')::boolean, false)     as is_ota_remedy,
    coalesce((payload->>'parkIt')::boolean, false)               as is_park_it,
    payload->>'Summary'                                          as summary,
    payload->>'Consequence'                                      as consequence,
    payload->>'Remedy'                                           as remedy
from src
