Инструкция по запуску
1. Клонирование репозитория
git clone https://github.com/Ilquora/autoria-scraper.git
cd autoria-scraper"
2. Создание файла окружения
Создайте файл .env в корне проекта со следующим содержимым:
(по подобию .env.example)
POSTGRES_DB=autoria
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123456
START_URL=https://auto.ria.com/car/used/
SCRAPING_TIME=12:00
DUMP_TIME=12:30
3. Запуск приложения
docker-compose up --build
4. Просмотр логов
Приложение начнет работать и выведет логи в консоль. При первом запуске:
Инициализируется база данных PostgreSQL
Создается таблица для хранения данных
Запускаются планировщики задач для скрапинга и дампов
5. Остановка приложения 
docker-compose down
Просмотр дампов базы данных
Дампы создаются в папке dumps в корне проекта. Имена файлов содержат дату и время создания:
# Пример: dump_20240627_120000.sql
Расписание настраивается в файле .env в формате cron:
SCRAPE_TIME - время запуска скрапинга
DUMP_TIME - время создания дампа БД
