-- SmartBite database schema (MySQL 8 / MariaDB 10.5+)
-- Usage:  mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS smartbite_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
--         mysql -u root -p smartbite_db < database.sql
-- The app also creates any missing table on start, but importing this file is the recommended setup.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('customer','restaurant_owner','rider','admin','staff') NOT NULL DEFAULT 'customer',
  phone VARCHAR(20),
  address TEXT,
  profile_image VARCHAR(255),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS restaurants (
  id INT AUTO_INCREMENT PRIMARY KEY,
  owner_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  address TEXT,
  phone VARCHAR(20),
  image VARCHAR(255),
  is_approved BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  is_open BOOLEAN NOT NULL DEFAULT TRUE,
  rating FLOAT DEFAULT 0,
  rating_count INT DEFAULT 0,
  delivery_time INT DEFAULT 35,
  bank_name VARCHAR(100),
  account_name VARCHAR(100),
  account_number VARCHAR(30),
  lat FLOAT,
  lng FLOAT,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rest_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS food_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  restaurant_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  price INT NOT NULL,
  category VARCHAR(50),
  image VARCHAR(255),
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_food_restaurant (restaurant_id),
  CONSTRAINT fk_food_rest FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  restaurant_id INT NOT NULL,
  rider_id INT NULL,
  subtotal INT NOT NULL DEFAULT 0,
  total_amount INT NOT NULL,
  service_charge INT NOT NULL DEFAULT 0,
  commission INT NOT NULL DEFAULT 0,
  rider_fee INT NOT NULL DEFAULT 0,
  status ENUM('placed','confirmed','preparing','out_for_delivery','delivered','cancelled') NOT NULL DEFAULT 'placed',
  rider_stage ENUM('assigned','picked','on_the_way','delivered') NULL,
  payment_method VARCHAR(20) NOT NULL DEFAULT 'cod',
  payment_status VARCHAR(30) NOT NULL DEFAULT 'pending',
  paystack_ref VARCHAR(100),
  delivery_address TEXT NOT NULL,
  customer_phone VARCHAR(20),
  lat FLOAT,
  lng FLOAT,
  note VARCHAR(255),
  is_packed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  delivered_at TIMESTAMP NULL,
  INDEX ix_orders_customer (customer_id),
  INDEX ix_orders_restaurant (restaurant_id),
  INDEX ix_orders_rider (rider_id),
  INDEX ix_orders_status (status),
  INDEX ix_orders_created (created_at),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES users(id),
  CONSTRAINT fk_orders_rest FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
  CONSTRAINT fk_orders_rider FOREIGN KEY (rider_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  food_id INT NULL,
  food_name VARCHAR(100) NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  price INT NOT NULL,
  INDEX ix_items_order (order_id),
  INDEX ix_items_food (food_id),
  CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_items_food FOREIGN KEY (food_id) REFERENCES food_items(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cart (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  food_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_cart_customer_food (customer_id, food_id),
  CONSTRAINT fk_cart_customer FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_cart_food FOREIGN KEY (food_id) REFERENCES food_items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  restaurant_id INT NOT NULL,
  order_id INT NULL UNIQUE,
  rating INT NOT NULL,
  comment TEXT,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_reviews_restaurant (restaurant_id),
  CONSTRAINT fk_reviews_customer FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_rest FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  method VARCHAR(50) NOT NULL,
  amount INT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reference VARCHAR(100),
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_pay_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS payment_proofs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  customer_id INT NOT NULL,
  image_path VARCHAR(255) NOT NULL,
  status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  note VARCHAR(255),
  uploaded_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_by INT NULL,
  reviewed_at TIMESTAMP NULL,
  INDEX ix_proofs_order (order_id),
  CONSTRAINT fk_proof_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_proof_customer FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_proof_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(150) NOT NULL,
  message VARCHAR(500),
  link VARCHAR(255),
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_notif_user (user_id),
  CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  kind VARCHAR(12) NOT NULL,
  target_id INT NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_favorite (user_id, kind, target_id),
  CONSTRAINT fk_fav_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS staff_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  restaurant_id INT NOT NULL,
  staff_role ENUM('cook','packager') NOT NULL,
  monthly_salary INT NOT NULL DEFAULT 0,
  hired_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_staff_rest (restaurant_id),
  CONSTRAINT fk_staff_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_staff_rest FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ads (
  id INT AUTO_INCREMENT PRIMARY KEY,
  restaurant_id INT NOT NULL,
  weeks INT NOT NULL,
  amount INT NOT NULL,
  proof_image VARCHAR(255),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  starts_at TIMESTAMP NULL,
  ends_at TIMESTAMP NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_ads_rest (restaurant_id),
  CONSTRAINT fk_ads_rest FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
  setting_key VARCHAR(50) PRIMARY KEY,
  setting_value TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fraud_flags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  user_id INT NOT NULL,
  reason VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_fraud_order (order_id),
  CONSTRAINT fk_fraud_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_fraud_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contact_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------------------
-- Required starting data (platform settings, food categories, first admin account)
-- ---------------------------------------------------------------------------------
INSERT IGNORE INTO settings (setting_key, setting_value) VALUES
  ('commission_percent', '10'), ('service_charge', '100'), ('ad_price_per_week', '5000'), ('rider_fee', '500'),
  ('admin_bank_name', ''), ('admin_account_name', ''), ('admin_account_number', ''),
  ('contact_email', ''), ('contact_phone', ''), ('contact_address', '');

INSERT IGNORE INTO categories (name) VALUES
  ('Rice Dishes'), ('Soups & Stews'), ('Grills & BBQ'), ('Fast Food'), ('Small Chops & Snacks'),
  ('Pasta'), ('Seafood'), ('Breakfast'), ('Drinks'), ('Desserts');

-- First admin: admin@smartbite.com / Admin@12345  (you are forced to change it on first login)
INSERT INTO users (name, email, password_hash, role, phone, address, is_active, must_change_password)
SELECT 'SmartBite Admin', 'admin@smartbite.com', 'scrypt:32768:8:1$SSgRmb0KlP8rubM5$c358eb48d1004a1e6da66154401d8eef1a8d174627401629d412bf80f536a08e8f2d91798321459325feac119c1c73c50e02a2d2587f51954b1a29ab901644bd', 'admin', '0000000000', 'SmartBite HQ', TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin');


-- Live GPS: latest location shared by a rider for each active assigned order.
CREATE TABLE IF NOT EXISTS rider_locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  rider_id INT NOT NULL,
  order_id INT NOT NULL,
  latitude DOUBLE NOT NULL,
  longitude DOUBLE NOT NULL,
  accuracy DOUBLE NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_rider_location_order (rider_id, order_id),
  INDEX ix_rider_locations_order (order_id),
  INDEX ix_rider_locations_rider (rider_id),
  CONSTRAINT fk_rider_locations_rider FOREIGN KEY (rider_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_rider_locations_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
