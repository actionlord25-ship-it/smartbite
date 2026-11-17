-- Run once against an existing SmartBite database.
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
