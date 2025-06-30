import os
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import asyncpg
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

DB_CONFIG = {
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("POSTGRES_DB"),
    "host": "db"
}
START_URL = os.getenv("START_URL", "https://auto.ria.com/car/used/")
SCRAPING_TIME = os.getenv("SCRAPING_TIME", "12:00")
DUMP_TIME = os.getenv("DUMP_TIME", "12:30")

async def create_db_pool():
    """Создает пул подключений к базе данных"""
    logger.info("Creating database connection pool")
    return await asyncpg.create_pool(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        host=DB_CONFIG["host"],
        min_size=1,
        max_size=10
    )

async def fetch_html(url):
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Request to {url} failed with status {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return None

def parse_car_page(html, url):
    """Парсит страницу автомобиля и извлекает данные"""
    soup = BeautifulSoup(html, 'lxml')
    
    title = soup.select_one('h1.head').text.strip() if soup.select_one('h1.head') else ""
    
    price_elem = soup.select_one('div.price_value strong')
    price = int(re.sub(r'\D', '', price_elem.text)) if price_elem else 0
    
    odometer_elem = soup.select_one('div.base-information span.size18')
    odometer_text = odometer_elem.text if odometer_elem else ""
    odometer = int(re.sub(r'\D', '', odometer_text)) * 1000 if 'тыс' in odometer_text else int(re.sub(r'\D', '', odometer_text))
    
    username_elem = soup.select_one('div.seller_info_name a')
    username = username_elem.text.strip() if username_elem else ""
    
    phone_elem = soup.select_one('div.phone_item')
    phone = phone_elem['data-phone-number'] if phone_elem and 'data-phone-number' in phone_elem.attrs else ""
    
    image_elem = soup.select_one('div.photo-620x465 img')
    image_url = image_elem['src'] if image_elem and 'src' in image_elem.attrs else ""
    
    images_count = len(soup.select('div.photo-620x465 img'))
    
    car_number_elem = soup.select_one('span.state-num')
    car_number = car_number_elem.text.strip() if car_number_elem else ""
    
    car_vin_elem = soup.select_one('span.label-vin')
    car_vin = car_vin_elem.text.strip() if car_vin_elem else ""
    
    return {
        "url": url,
        "title": title,
        "price_usd": price,
        "odometer": odometer,
        "username": username,
        "phone_number": phone,
        "image_url": image_url,
        "images_count": images_count,
        "car_number": car_number,
        "car_vin": car_vin
    }

async def get_all_pages(base_url):
    logger.info(f"Getting all pages from {base_url}")
    html = await fetch_html(base_url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    last_page = 1
    page_links = soup.select('span.page-item:not(.next) a')
    if page_links:
        page_numbers = [int(link.text) for link in page_links if link.text.isdigit()]
        if page_numbers:
            last_page = max(page_numbers)
    
    return [f"{base_url}?page={i}" for i in range(1, last_page + 1)]

async def get_car_links(page_url):
    logger.info(f"Getting car links from {page_url}")
    html = await fetch_html(page_url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    links = []
    for item in soup.select('a.m-link-ticket'):
        if href := item.get('href'):
            links.append(href)
    return links

async def save_car_data(pool, car_data):
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO car_listings (
                    url, title, price_usd, odometer, username, 
                    phone_number, image_url, images_count, car_number, car_vin
                ) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (url) DO NOTHING
            """, 
            car_data['url'], car_data['title'], car_data['price_usd'], 
            car_data['odometer'], car_data['username'], car_data['phone_number'],
            car_data['image_url'], car_data['images_count'], 
            car_data['car_number'], car_data['car_vin'])
            logger.info(f"Saved car: {car_data['title']}")
        except Exception as e:
            logger.error(f"Error saving car {car_data['url']}: {str(e)}")

async def scrape_site():
    """Основная функция скрапинга сайта"""
    logger.info("Starting scraping process")
    try:
        pool = await create_db_pool()
        page_urls = await get_all_pages(START_URL)
        
        for page_url in page_urls:
            try:
                car_urls = await get_car_links(page_url)
                logger.info(f"Found {len(car_urls)} cars on page {page_url}")
                
                for car_url in car_urls:
                    try:
                        html = await fetch_html(car_url)
                        if html:
                            car_data = parse_car_page(html, car_url)
                            await save_car_data(pool, car_data)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error processing car {car_url}: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing page {page_url}: {str(e)}")
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
    finally:
        if 'pool' in locals():
            await pool.close()
    logger.info("Scraping completed")

def create_dump():
    logger.info("Creating database dump")
    try:
        os.makedirs("dumps", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        dump_file = f"dumps/dump_{timestamp}.sql"
        
        subprocess.run([
            "pg_dump",
            "-h", "db",
            "-U", DB_CONFIG["user"],
            "-d", DB_CONFIG["database"],
            "-f", dump_file
        ], 
        env={"PGPASSWORD": DB_CONFIG["password"]},
        check=True)
        logger.info(f"Dump created: {dump_file}")
    except Exception as e:
        logger.error(f"Dump failed: {str(e)}")

async def main():
    logger.info("Application starting")
   
    scheduler = AsyncIOScheduler()
    
    scraping_hour, scraping_minute = map(int, SCRAPING_TIME.split(':'))
    scheduler.add_job(scrape_site, 'cron', hour=scraping_hour, minute=scraping_minute)
    
    dump_hour, dump_minute = map(int, DUMP_TIME.split(':'))
    scheduler.add_job(create_dump, 'cron', hour=dump_hour, minute=dump_minute)
    

    scheduler.start()
    logger.info(f"Scheduler started. Scraping at {SCRAPING_TIME}, dumps at {DUMP_TIME}")
    
  
    await scrape_site()
    create_dump()

    logger.info("Entering main loop")
    while True:
        await asyncio.sleep(3600) 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")