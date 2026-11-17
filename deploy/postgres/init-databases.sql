-- One PostgreSQL server, one database per service (auth_db is shared by Registration, Login and Member
-- because they all work on the same `users` table).
CREATE DATABASE auth_db;
CREATE DATABASE catalog_db;
CREATE DATABASE inventory_db;
CREATE DATABASE borrowing_db;
CREATE DATABASE fine_db;
CREATE DATABASE review_db;
