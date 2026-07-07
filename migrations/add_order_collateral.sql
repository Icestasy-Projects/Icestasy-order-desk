-- Marketing collateral dispatched with (or independently of) an order.
create table if not exists sales.order_collateral (
    id bigint generated always as identity primary key,
    order_id integer not null references sales.orders(id),
    collateral_type text not null,
    quantity integer not null,
    notes text,
    created_at timestamptz not null default now()
);

create index if not exists idx_order_collateral_order_id on sales.order_collateral (order_id);
