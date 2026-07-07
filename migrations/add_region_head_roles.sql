-- Regional head roles: each sees orders/team scoped to their city region only.
-- ROI = "Rest of India" catch-all for anywhere outside the named 5 metros.
alter type sales.user_role add value 'mumbai_head';
alter type sales.user_role add value 'pune_head';
alter type sales.user_role add value 'bangalore_head';
alter type sales.user_role add value 'hyderabad_head';
alter type sales.user_role add value 'delhi_head';
alter type sales.user_role add value 'roi_head';

-- Which region a staff member belongs to (for regional heads' team roster).
-- Not meaningful for manager/onboarding/region-head rows themselves.
alter table sales.users add column region text;
