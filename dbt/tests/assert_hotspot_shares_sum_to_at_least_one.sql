-- A complaint can hit several component groups, so shares per vehicle sum to >= 1, never less.
select make, model, model_year, sum(share) as total_share
from {{ ref('agg_component_hotspots') }}
group by 1, 2, 3
having sum(share) < 0.999
