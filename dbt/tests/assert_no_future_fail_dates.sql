{{ config(severity="warn") }}
-- A failure can't happen after NHTSA received the complaint (small tolerance for data entry).
select odi_number, fail_date, received_date
from {{ ref('stg_complaints') }}
where fail_date > received_date + interval '1 day'
