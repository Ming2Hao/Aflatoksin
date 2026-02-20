-- MySQL schema untuk menyimpan hasil grading aflatoksin
-- Default database: aflatoksin (sesuaikan dengan env MYSQL_DATABASE)

-- CREATE DATABASE IF NOT EXISTS aflatoksin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE aflatoksin;

CREATE TABLE IF NOT EXISTS grading_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  captured_at DATETIME NOT NULL,
  final_grade VARCHAR(32) NOT NULL,
  total_area_pixels INT UNSIGNED NOT NULL,
  total_area_percentage DECIMAL(10,6) NOT NULL,
  total_objects INT UNSIGNED NOT NULL,

  reject_total_pixels INT UNSIGNED NOT NULL,
  reject_total_objects INT UNSIGNED NOT NULL,
  grade_d_total_pixels INT UNSIGNED NOT NULL,
  grade_d_total_objects INT UNSIGNED NOT NULL,
  grade_c_total_pixels INT UNSIGNED NOT NULL,
  grade_c_total_objects INT UNSIGNED NOT NULL,

  original_image_path VARCHAR(512) NOT NULL,
  graded_image_path VARCHAR(512) NOT NULL,

  -- Menyimpan ringkasan (tanpa bounding box / list objek) sebagai JSON
  detail_json JSON NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_captured_at (captured_at),
  KEY idx_final_grade (final_grade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
