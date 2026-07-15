-- The old order-number generator computed the next sequence by SELECTing
-- every existing order_no matching a city/FY pattern and taking the max
-- client-side. PostgREST caps that SELECT at 1000 rows by default, so any
-- city/FY with more orders than that (Mumbai FY26-27 has 2,394) silently
-- got a stale, too-low max — producing an order_no that collided with a
-- real existing order and made order creation fail outright. The read-then-
-- write approach was also racy under concurrent order creation regardless
-- of row count.
--
-- Replaced with an atomic Postgres-side counter: one row per (city, FY),
-- incremented via next_order_seq() using INSERT ... ON CONFLICT DO UPDATE,
-- which Postgres serializes with a row lock.
create table sales.order_sequences (
  city_code text not null,
  fy text not null,
  last_seq integer not null default 0,
  primary key (city_code, fy)
);

create or replace function sales.next_order_seq(p_city_code text, p_fy text)
returns integer
language plpgsql
as $$
declare
  v_seq integer;
begin
  insert into sales.order_sequences (city_code, fy, last_seq)
  values (p_city_code, p_fy, 1)
  on conflict (city_code, fy)
  do update set last_seq = sales.order_sequences.last_seq + 1
  returning last_seq into v_seq;
  return v_seq;
end;
$$;

-- Backfill with the true max sequence per city/FY, computed here via direct
-- SQL rather than the capped REST scan that caused the bug in the first
-- place.
insert into sales.order_sequences (city_code, fy, last_seq)
select
  substring(order_no from '^(MU|PU|BA|HY|DL|ROI)') as city_code,
  substring(order_no from '/(\d{2}-\d{2})/') as fy,
  max(substring(order_no from '/(\d+)$')::int) as last_seq
from sales.orders
where order_no ~ '^(MU|PU|BA|HY|DL|ROI)[0-9]{2}/[0-9]{2}-[0-9]{2}/[0-9]+$'
group by 1, 2;
