{# NHTSA date fields contain junk (00000000, 20211332, 30/02/...). to_date() raises on those,
   so wrap it: bad values become NULL instead of failing the whole build. #}
{% macro create_try_date() %}
create or replace function public.try_date(val text, fmt text) returns date
language plpgsql immutable as $$
begin
    if val is null or btrim(val) = '' then return null; end if;
    return to_date(val, fmt);
exception when others then
    return null;
end;
$$;
{% endmacro %}
