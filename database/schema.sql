-- ClipQueue database schema (MySQL 8)
-- WARNING: this script DELETES and recreates the tables.
-- Use it only while developing, before real data is entered.

CREATE DATABASE IF NOT EXISTS clipqueue_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE clipqueue_db;

-- Remove old tables first (children before parents, because of foreign keys)
DROP TABLE IF EXISTS faqs;
DROP TABLE IF EXISTS shop_settings;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS barber_schedules;
DROP TABLE IF EXISTS barber_services;
DROP TABLE IF EXISTS barber_specialties;
DROP TABLE IF EXISTS specialties;
DROP TABLE IF EXISTS barbers;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS users;


-- 1. USERS: customers, staff, administrators
CREATE TABLE users (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('administrator', 'staff', 'customer') NOT NULL DEFAULT 'customer',
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- 2. SERVICES: what the shop offers
CREATE TABLE services (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(100) NOT NULL UNIQUE,
    description      TEXT,
    price            DECIMAL(8,2) NOT NULL,
    duration_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 30,
    is_active        TINYINT(1) NOT NULL DEFAULT 1,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (price >= 0),
    CHECK (duration_minutes > 0)
) ENGINE=InnoDB;


-- 3. BARBERS: profiles (barbers do not log in)
CREATE TABLE barbers (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    bio          TEXT,
    barber_type  ENUM('owner', 'independent') NOT NULL DEFAULT 'independent',
    is_active    TINYINT(1) NOT NULL DEFAULT 1,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- 4. SPECIALTIES: tags such as "Fades" or "Beard Styling"
CREATE TABLE specialties (
    id   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;


-- 5. BARBER_SPECIALTIES: which barber has which specialty (many-to-many)
CREATE TABLE barber_specialties (
    barber_id    INT UNSIGNED NOT NULL,
    specialty_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (barber_id, specialty_id),
    FOREIGN KEY (barber_id)    REFERENCES barbers(id)     ON DELETE CASCADE,
    FOREIGN KEY (specialty_id) REFERENCES specialties(id) ON DELETE CASCADE
) ENGINE=InnoDB;


-- 6. BARBER_SERVICES: which barber offers which service (many-to-many)
CREATE TABLE barber_services (
    barber_id  INT UNSIGNED NOT NULL,
    service_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (barber_id, service_id),
    FOREIGN KEY (barber_id)  REFERENCES barbers(id)  ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
) ENGINE=InnoDB;


-- 7. BARBER_SCHEDULES: usual weekly working hours (NOT appointment slots)
--    day_of_week: 1 = Monday, 2 = Tuesday, ... 7 = Sunday
--    One row per barber per working day.
CREATE TABLE barber_schedules (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    barber_id   INT UNSIGNED NOT NULL,
    day_of_week TINYINT UNSIGNED NOT NULL,
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    UNIQUE (barber_id, day_of_week),
    CHECK (day_of_week BETWEEN 1 AND 7),
    CHECK (end_time > start_time),
    FOREIGN KEY (barber_id) REFERENCES barbers(id) ON DELETE CASCADE
) ENGINE=InnoDB;


-- 8. APPOINTMENTS: bookings made by customers
CREATE TABLE appointments (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    booking_reference VARCHAR(12) NOT NULL UNIQUE,
    customer_id       INT UNSIGNED NOT NULL,
    barber_id         INT UNSIGNED NOT NULL,
    service_id        INT UNSIGNED NOT NULL,
    appointment_date  DATE NOT NULL,
    start_time        TIME NOT NULL,
    end_time          TIME NOT NULL,
    status            ENUM('pending', 'confirmed', 'completed', 'cancelled')
                      NOT NULL DEFAULT 'pending',
    notes             VARCHAR(255),
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_time > start_time),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (barber_id)   REFERENCES barbers(id),
    FOREIGN KEY (service_id)  REFERENCES services(id),
    INDEX idx_barber_slot (barber_id, appointment_date, start_time)
) ENGINE=InnoDB;


-- 9. FEEDBACK: customer reviews (staff approve before they are shown)
CREATE TABLE feedback (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    customer_id    INT UNSIGNED NOT NULL,
    appointment_id INT UNSIGNED NULL UNIQUE,
    barber_id      INT UNSIGNED NULL,
    rating         TINYINT UNSIGNED NOT NULL,
    comment        VARCHAR(1000) NOT NULL,
    status         ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (rating BETWEEN 1 AND 5),
    FOREIGN KEY (customer_id)    REFERENCES users(id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
    FOREIGN KEY (barber_id)      REFERENCES barbers(id)      ON DELETE SET NULL
) ENGINE=InnoDB;