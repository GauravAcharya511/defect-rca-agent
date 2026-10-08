-- Recalls with their component group. Stage 5 uses these as ground truth:
-- "given the complaints for this vehicle, does the agent point at the recalled component?"
select
    campaign_number, make, model, model_year,
    component, component_group,
    report_received_date, is_ota_remedy, is_park_it,
    summary, consequence, remedy
from {{ ref('stg_recalls') }}
