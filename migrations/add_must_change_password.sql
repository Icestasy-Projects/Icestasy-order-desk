-- New staff accounts get a default password and must change it on first login.
alter table sales.users add column must_change_password boolean not null default false;
