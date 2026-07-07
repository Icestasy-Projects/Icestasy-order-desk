-- Dedicated role for the person(s) allowed to register new clients,
-- distinct from Head of Sales (manager) and regular salespeople.
alter type sales.user_role add value 'onboarding';
