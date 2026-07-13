-- Tax invoice generation needs an HSN/SAC code and a GST rate per SKU.
-- Neither existed anywhere before. Default HSN (21050000, "Ice cream and
-- other edible ice") and 5% GST match the reference invoice; admin can
-- override per SKU in the Flavours tab.
alter table sales.skus add column if not exists hsn_code text;
alter table sales.skus add column if not exists gst_rate numeric(5,2) not null default 5.00;
update sales.skus set hsn_code = '21050000' where hsn_code is null;
