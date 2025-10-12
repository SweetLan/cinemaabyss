# Диаграмма компонентов CinemaAbyss "Recommendations Adapter — Component Diagram"

```plantuml
@startuml
title Recommendations Adapter Component Diagram (Интеграция с системой рекомендаций)

top to bottom direction

!includeurl https://raw.githubusercontent.com/RicardoNiepel/C4-PlantUML/master/C4_Component.puml

Container_Boundary(recAdapter, "Recommendations Adapter (Go)") {

  Component(api, "Recommendations API", "Go (HTTP)", "Единая REST-точка для внутренних сервисов")
  Component(mapper, "Request/Response Mapper", "Go", "Маппинг DTO ⇄ AMQP payload, headers, routing keys")
  Component(codec, "Codec/Schema", "Go", "Сериализация/валидация JSON/Avro, версии схем")
  Component(prod, "Rabbit Producer", "Go (AMQP)", "Публикация запросов (request) c correlationId")
  Component(cons, "Rabbit Consumer", "Go (AMQP)", "Чтение reply по correlationId из reply-очереди")
  Component(cache, "Result Cache", "Redis", "Кэш рекомендаций (TTL) и защита от шторма")
  Component(ctrl, "SLA Control", "Go", "Timeout/Retry/Backoff, circuit-breaker")
}

' --- Внешнее окружение компонента
Container_Ext(apiGw, "API Gateway / Ingress", "Edge")
Container_Ext(metadata, "Metadata Service", "Внутренний сервис (клиент адаптера)")
System_Ext(rabbitReco, "RabbitMQ (шина рекомендаций)", "Внешний брокер")
System_Ext(reco, "Recommendation Engine", "Внешняя система")

' --- Потоки
Rel(apiGw, api, "REST/JSON", "HTTPS")
Rel(metadata, api, "REST/JSON", "HTTPS")

Rel(api, mapper, "DTO")
Rel(mapper, codec, "Сериализация/валидация")
Rel(mapper, prod, "Publish request", "AMQP")
Rel(prod, rabbitReco, "AMQP")

Rel(rabbitReco, cons, "Reply messages", "AMQP")
Rel(cons, codec, "Десериализация/валидация")
Rel(cons, cache, "Обновление кэша")
Rel(api, cache, "Get (cache-first) / set-on-miss")
Rel(ctrl, api, "Таймауты/ретраи/CB")

' Ответ вызывающему
Rel(cons, api, "Корреляция по correlationId → HTTP response")

' Взаимосвязь брокера и внешнего движка
Rel(rabbitReco, reco, "AMQP routing/bindings")

@enduml
```
