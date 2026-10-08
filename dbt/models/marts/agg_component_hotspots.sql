-- Which component groups are over-represented for each vehicle?
-- We have no sales/fleet counts, so this is complaint SHARE, not a failure rate:
--   share      = component complaints / all complaints for that vehicle-year
--   baseline   = average of that share across vehicle-years, each vehicle-year weighted
--                equally (a vehicle-year with no such complaints counts as 0), so the
--                makes with the most vehicle-years (Tesla here) don't define "normal"
--   hotspot_ix = share / baseline  (2.0 = twice as common as the typical vehicle)
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
shares as (
    select p.make, p.model, p.model_year, p.component_group, p.complaints, t.vehicle_complaints,
           p.complaints::numeric / t.vehicle_complaints as share
    from per_vehicle p
    join vehicle_totals t using (make, model, model_year)
),
grid as (
    select v.make, v.model, v.model_year, g.component_group
    from vehicle_totals v
    cross join (select distinct component_group from per_vehicle) g
),
baseline as (
    select g.component_group, avg(coalesce(s.share, 0)) as baseline_share
    from grid g
    left join shares s using (make, model, model_year, component_group)
    group by 1
)
select
    s.make, s.model, s.model_year, s.component_group,
    s.complaints,
    s.vehicle_complaints,
    round(s.share, 4)                       as share,
    round(b.baseline_share, 4)              as baseline_share,
    round(s.share / b.baseline_share, 2)    as hotspot_ix,
    rank() over (partition by s.make, s.model, s.model_year order by s.complaints desc) as rank_in_vehicle
from shares s
join baseline b using (component_group)
