# Диаграмма контейнеров CinemaAbyss

```plantuml
@startuml container
title "Кинобездна (CinemaAbyss) — Диаграмма контейнеров TO-BE"

top to bottom direction

!includeurl https://raw.githubusercontent.com/RicardoNiepel/C4-PlantUML/master/C4_Container.puml

Person(user, "Пользователь", "Смотрит контент, ставит оценки, ведёт избранное, оформляет подписку")
Person(admin, "Администратор", "Управление тарифами, модерация контента, промо-активности")
System(cinema, "Кинобездна", "Онлайн-кинотеатр-агрегатор")



Container_Boundary(cinema, "Кинобездна (Kubernetes)") {
  Container(web, "Web / Mobile / TV UI", "SPA/Native", "Клиентские приложения (веб/мобайл/TV)")
  Container(apiGw, "API Gateway / Ingress", "NGINX / Kong", "Единая точка входа в систему")

  Container(auth, "Auth Service", "Go", "Регистрация, логин, выдача JWT, роли")
  Container(profile, "Profile Service", "Go", "Профили пользователей")
  Container(metadata, "Metadata Service", "Go", "Карточки фильмов, жанры, актёры")
  Container(search, "Search API", "Go", "Поиск/фильтрация по каталогу")
  Container(fav, "Favorites & Ratings", "Go", "Избранное и пользовательские оценки")
  Container(ingest, "Content Ingestion", "Go", "Импорт метаданных и загрузка объектов в S3")

  Container(subs, "Subscriptions Service", "Go", "Планы и статусы подписок")
  Container(payments, "Payments Orchestrator", "Go", "Оркестрация платежей, коллбеки платёжных шлюзов")

  Container(recAdapter, "Recommendations Adapter", "Go", "Адаптер к внешней рекомендационной системе")
  Container(kafka, "Kafka (Event Bus)", "Apache Kafka", "Внутренние события (MVP)")

  ContainerDb(dbUsers, "Users DB", "PostgreSQL", "Учётные записи, профили")
  ContainerDb(dbCatalog, "Catalog DB", "PostgreSQL", "Метаданные фильмов")
  ContainerDb(dbRates, "Ratings DB", "PostgreSQL", "Оценки и избранное")
  ContainerDb(dbSubs, "Subscriptions DB", "PostgreSQL", "Подписки")
  ContainerDb(dbPay, "Payments DB", "PostgreSQL", "Платёжные сессии, статусы")
  Container(cache, "Cache", "Redis", "Кэш каталога/профилей/избранного")
  Container(s3, "Object Storage (S3)", "S3-compatible", "Видео/статический контент/постеры/тизеры/датасеты (datalake)")

}

System_Ext(pay, "Платёжные шлюзы", "Платежные системы")
System_Ext(reco, "Рекомендательная система", "Внешняя рекомндательная система")
System_Ext(rabbitReco, "RabbitMQ (шина рекомендаций)", "Внешний брокер, через который работает reco")

' --- Пользователи → система
Rel(user, web, "Использует", "HTTPS")
Rel(admin, web, "Администрирует", "HTTPS")
Rel(web, apiGw, "REST/JSON", "HTTPS")

' --- API Gateway → сервисы
Rel(apiGw, auth, "REST/JSON + JWT")
Rel(apiGw, profile, "REST/JSON")
Rel(apiGw, metadata, "REST/JSON")
Rel(apiGw, search, "REST/JSON")
Rel(apiGw, fav, "REST/JSON")
Rel(apiGw, ingest, "REST/JSON")
Rel(apiGw, subs, "REST/JSON")
Rel(apiGw, payments, "REST/JSON")
Rel(apiGw, recAdapter, "REST/JSON")

' --- Рекомендации
Rel(metadata, recAdapter, "Запросы рекоменд. списков", "REST")
Rel(recAdapter, rabbitReco, "Publish/Consume (request/reply)", "AMQP/RabbitMQ")
Rel(rabbitReco, reco, "Доставка сообщений к внешнему движку", "AMQP")

' --- Платежи
Rel(subs, payments, "Создание/проверка платежа", "REST")
Rel(payments, pay, "Инициация платежа", "HTTPS/REST")
Rel(pay, payments, "Webhook: success/fail/cancel", "HTTPS")


' --- События (внутренние)
Rel(auth, kafka, "events")
Rel(profile, kafka, "events")
Rel(metadata, kafka, "events")
Rel(search, kafka, "events")
Rel(fav, kafka, "events")
Rel(subs, kafka, "events")
Rel(payments, kafka, "events")

' --- Данные
Rel(auth, dbUsers, "SQL")
Rel(profile, dbUsers, "SQL")
Rel(metadata, dbCatalog, "SQL")
Rel(search, dbCatalog, "read")
Rel(fav, dbRates, "SQL")
Rel(subs, dbSubs, "SQL")
Rel(payments, dbPay, "SQL")

Rel_R(web, cache, "cache")
Rel_R(metadata, cache, "cache")
Rel_R(fav, cache, "cache")
Rel_R(profile, cache, "cache")

Rel(ingest, s3, "Загрузка объектов (видео/статик/датасеты)", "S3 API")

@enduml

```