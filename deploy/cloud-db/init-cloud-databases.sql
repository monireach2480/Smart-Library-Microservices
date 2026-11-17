-- Smart Library - create the six databases on a CLOUD PostgreSQL instance.
--
-- Guideline 4 forbids a database container, so this runs once against a managed PostgreSQL
-- (Neon, Supabase, Amazon RDS, Aiven, Azure Database for PostgreSQL ...) before the cluster starts.
-- The tables inside each database are then created automatically by each service on first start
-- (SQLAlchemy `init_db()` in app/core/database.py).
--
-- Run it with psql, connected to the provider's default database:
--     psql "postgresql://USER:PASSWORD@HOST/postgres?sslmode=require" -f deploy/cloud-db/init-cloud-databases.sql
-- or paste the statements one at a time into the provider's web SQL console.
--
-- CREATE DATABASE cannot run inside a transaction block, so execute these as separate statements.

-- Shared by Registration, Login and Member: they all work on the same `users` table.
CREATE DATABASE auth_db;

CREATE DATABASE catalog_db;
CREATE DATABASE inventory_db;
CREATE DATABASE borrowing_db;
CREATE DATABASE fine_db;
CREATE DATABASE review_db;

-- ---------------------------------------------------------------------------------------------
-- Providers that allow only ONE database on the free tier (e.g. Supabase):
-- use one schema per service inside the single database instead, and append
-- `&options=-csearch_path%3D<schema>` to that service's DATABASE_URL.
--
--   CREATE SCHEMA auth;
--   CREATE SCHEMA catalog;
--   CREATE SCHEMA inventory;
--   CREATE SCHEMA borrowing;
--   CREATE SCHEMA fine;
--   CREATE SCHEMA review;
-- ---------------------------------------------------------------------------------------------
