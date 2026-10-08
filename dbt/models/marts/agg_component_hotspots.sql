-- Which component groups are over-represented for each vehicle?
-- We have no sales/fleet counts, so this is complaint SHARE, not a failure rate:
--   share      = component complaints / all complaints for that vehicle-year
--   baseline   = the same component's share across every vehicle in scope
--   hotspot_ix = share / baseline  (2.0 = twice as common as usual)
with per_vehicle as (
    select make, model, model_year, component_group,
           count(distinct odi_number) as complaints
    from {{ ref('stg_complaints') }}
    group by 1, 2, 3, 4
),
vehicle_totals as (
    select make, model, model_year, count(distinct odi_number) as vehicle_complaints
    from {{ ref('stg_complaints') }}
    group by 1, 2, 3
),
baseline as (
    select component_group,
           count(distinct odi_number)::numeric
             / (select count(distinct odi_number) from {{ ref('stg_complaints') }}) as baseline_share
    from {{ ref('stg_complaints') }}
    group by 1
)
select
    p.make, p.model, p.model_year, p.component_group,
    p.complaints,
    t.vehicle_complaints,
    round(p.complaints::numeric / t.vehicle_complaints, 4)                  as share,
    round(b.baseline_share, 4)                                             as baseline_share,
    round((p.complaints::numeric / t.vehicle_complaints) / b.baseline_share, 2) as hotspot_ix,
    rank() over (partition by p.make, p.model, p.model_year order by p.complaints desc) as rank_in_vehicle
from per_vehicle p
join vehicle_totals t using (make, model, model_year)
join baseline b using (component_group)
