-- One row per complaint per vehicle (components collapsed). This is the unit the
-- retrieval layer embeds in Stage 3: one narrative, many tagged components.
select
    odi_number,
    make,
    model,
    model_year,
    min(fail_date)                                   as fail_date,
    min(received_date)                               as received_date,
    bool_or(is_crash)                                as is_crash,
    bool_or(is_fire)                                 as is_fire,
    max(injuries)                                    as injuries,
    max(deaths)                                      as deaths,
    max(miles)                                       as miles,
    array_agg(distinct component order by component) as components,
    array_agg(distinct component_group order by component_group) as component_groups,
    max(description)                                 as description
from {{ ref('stg_complaints') }}
group by 1, 2, 3, 4
