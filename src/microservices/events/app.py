import os, json, asyncio, logging
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer, AIOKafkaAdminClient
from aiokafka.admin import NewTopic

# ----- конфиг -----
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "events-service")

TOPIC_USER = "events.user"
TOPIC_PAYMENT = "events.payment"
TOPIC_MOVIE = "events.movie"
TOPICS = [TOPIC_USER, TOPIC_PAYMENT, TOPIC_MOVIE]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("events")

app = FastAPI(title="CinemaAbyss Events Service")

producer: Optional[AIOKafkaProducer] = None
consumer_task: Optional[asyncio.Task] = None

class EventIn(BaseModel):
    type: Literal["User", "Payment", "Movie"] = Field(..., description="Тип события")
    payload: dict = Field(default_factory=dict, description="Произвольные данные события")

def topic_for(evt_type: str) -> str:
    return {
        "User": TOPIC_USER,
        "Payment": TOPIC_PAYMENT,
        "Movie": TOPIC_MOVIE,
    }[evt_type]

async def ensure_topics():
    """Создаём топики, если их ещё нет."""
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        to_create = [t for t in TOPICS if t not in existing]
        if to_create:
            log.info(f"Creating topics: {to_create}")
            new_topics = [NewTopic(name=t, num_partitions=1, replication_factor=1) for t in to_create]
            await admin.create_topics(new_topics=new_topics, validate_only=False)
    finally:
        await admin.close()

async def run_consumer():
    """Фоновый consumer: читает все три топика и пишет в лог."""
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=GROUP_ID,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    log.info("Kafka consumer started")
    try:
        async for msg in consumer:
            try:
                value = msg.value.decode("utf-8")
            except Exception:
                value = str(msg.value)
            log.info(f"[consume] topic={msg.topic} partition={msg.partition} offset={msg.offset} value={value}")
    finally:
        await consumer.stop()
        log.info("Kafka consumer stopped")

@app.on_event("startup")
async def on_startup():
    global producer, consumer_task
    await ensure_topics()
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    consumer_task = asyncio.create_task(run_consumer())
    log.info("Kafka producer started")

@app.on_event("shutdown")
async def on_shutdown():
    global producer, consumer_task
    if producer:
        await producer.stop()
    if consumer_task:
        consumer_task.cancel()

@app.get("/healthz")
async def healthz():
    return {"status": True, "bootstrap": KAFKA_BOOTSTRAP, "group": GROUP_ID, "topics": TOPICS}

@app.post("/api/events")
async def create_event(evt: EventIn):
    """Создаёт событие и возвращает, в какой топик оно отправлено."""
    if not producer:
        raise HTTPException(status_code=503, detail="producer not ready")

    topic = topic_for(evt.type)
    payload = evt.model_dump()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        md = await producer.send_and_wait(topic, value=data)
        log.info(f"[produce] topic={topic} metadata={md.topic}:{md.partition}@{md.offset} value={payload}")
        return {"status": "queued", "topic": topic, "offset": md.offset}
    except Exception as e:
        log.exception("produce failed")
        raise HTTPException(status_code=500, detail=f"produce failed: {e}")
