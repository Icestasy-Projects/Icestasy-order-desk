-- Marketing collateral library, standalone from orders (own tab in the UI).
create table if not exists sales.order_collateral (
    id bigint generated always as identity primary key,
    title text not null,
    description text,
    category text not null default 'general',
    file_url text not null,
    created_by integer,
    created_at timestamptz not null default now()
);

create index if not exists idx_order_collateral_category on sales.order_collateral (category);
create index if not exists idx_order_collateral_created_at on sales.order_collateral (created_at desc);
