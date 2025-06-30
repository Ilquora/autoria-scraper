

CREATE TABLE IF NOT EXISTS car_listings (
    id SERIAL PRIMARY KEY,
    url VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    price_usd INTEGER NOT NULL,
    odometer INTEGER NOT NULL,
    username VARCHAR(100),
    phone_number VARCHAR(20),
    image_url VARCHAR(255),
    images_count INTEGER,
    car_number VARCHAR(20),
    car_vin VARCHAR(50),
    datetime_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);