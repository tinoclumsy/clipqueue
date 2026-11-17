-- ClipQueue SAMPLE DATA
-- Everything here is made up for testing. Names, prices, and hours are NOT real.
-- Replace it with the shop's real information later.
-- Run this only ONCE, right after schema.sql (it assumes empty tables).

USE clipqueue_db;

-- Services (ids will be 1 to 4)
INSERT INTO services (name, description, price, duration_minutes) VALUES
('Sample Haircut',       'SAMPLE: a regular haircut. Replace with the real description.',   100.00, 30),
('Sample Beard Trim',    'SAMPLE: shaping and trimming the beard. Replace with real info.',  80.00, 30),
('Sample Hair Coloring', 'SAMPLE: hair color service. Replace with real info.',             500.00, 60),
('Sample Kids Haircut',  'SAMPLE: haircut for children. Replace with real info.',            80.00, 30);

-- Barbers (ids will be 1 to 3)
INSERT INTO barbers (display_name, bio, barber_type) VALUES
('Sample Barber A', 'SAMPLE profile. Replace with the real barber''s details.', 'owner'),
('Sample Barber B', 'SAMPLE profile. Replace with the real barber''s details.', 'independent'),
('Sample Barber C', 'SAMPLE profile. Replace with the real barber''s details.', 'independent');

-- Specialties (ids will be 1 to 4)
INSERT INTO specialties (name) VALUES
('Classic Cuts'),
('Fades'),
('Beard Styling'),
('Hair Coloring');

-- Which barber has which specialty
-- A (1): Classic Cuts, Fades | B (2): Beard Styling | C (3): Hair Coloring
INSERT INTO barber_specialties (barber_id, specialty_id) VALUES
(1, 1), (1, 2),
(2, 3),
(3, 4);

-- Which barber offers which service
-- A (1): Haircut, Kids Haircut | B (2): Haircut, Beard Trim | C (3): Hair Coloring
INSERT INTO barber_services (barber_id, service_id) VALUES
(1, 1), (1, 4),
(2, 1), (2, 2),
(3, 3);

-- Weekly working hours (1 = Monday ... 7 = Sunday)
-- A works Mon-Wed, B works Wed-Sat, C works Fri-Sun
INSERT INTO barber_schedules (barber_id, day_of_week, start_time, end_time) VALUES
(1, 1, '09:00:00', '17:00:00'),
(1, 2, '09:00:00', '17:00:00'),
(1, 3, '09:00:00', '17:00:00'),
(2, 3, '10:00:00', '18:00:00'),
(2, 4, '10:00:00', '18:00:00'),
(2, 5, '10:00:00', '18:00:00'),
(2, 6, '10:00:00', '18:00:00'),
(3, 5, '12:00:00', '19:00:00'),
(3, 6, '12:00:00', '19:00:00'),
(3, 7, '12:00:00', '19:00:00');