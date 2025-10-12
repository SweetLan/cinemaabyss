# Контекстная диаграмма CinemaAbyss

```plantuml
@startuml context-diagram
!includeurl https://raw.githubusercontent.com/RicardoNiepel/C4-PlantUML/master/C4_Context.puml

title "Кинобездна (CinemaAbyss) — Контекстная диаграмма TO-BE"
top to bottom direction

Person(user, "Пользователь", "Смотрит контент, ставит оценки, ведёт избранное, оформляет подписку")
Person(admin, "Администратор", "Управление тарифами, модерация контента, промо-активности")
System(cinema, "Кинобездна", "Онлайн-кинотеатр-агрегатор")


System_Ext(pay, "Платёжные шлюзы", "Платежные системы")
System_Ext(reco, "Рекомендательная система", "Внешняя рекомндательная система")


Rel(user, cinema, "Смотрит каталог, оформляет/продлевает подписку, ставит оценки", "HTTPS / Web & Mobile & TV")
Rel(admin, cinema, "Управляет контентом", "HTTPS / Admin UI")

Rel(cinema, pay, "Оплата/возвраты, 3-DS, нотификации", "HTTPS / REST, Webhook")
Rel(cinema, reco, "Запрос рекомендаций и обратная связь (оценки/просмотры)", "HTTPS / REST, Async events")
@enduml
```