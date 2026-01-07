import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from confluent_kafka import Consumer, Producer, KafkaException
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pythonjsonlogger import jsonlogger

# -------------------------
# Настройки
# -------------------------
PORT = int(os.getenv("PORT", "8082"))
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")

TOPIC_MOVIE = os.getenv("TOPIC_MOVIE", "movie-events")
TOPIC_USER = os.getenv("TOPIC_USER", "user-events")
TOPIC_PAYMENT = os.getenv("TOPIC_PAYMENT", "payment-events")

CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID", "events-service")

# -------------------------
# Логи
# -------------------------
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
root_logger.handlers.clear()
root_logger.addHandler(handler)

logger = logging.getLogger("events-service")

# -------------------------
# Модель данных
# -------------------------
class MovieEvent(BaseModel):
    movie_id: int
    title: str
    action: str
    user_id: Optional[int] = None
    rating: Optional[float] = None
    genres: Optional[List[str]] = None
    description: Optional[str] = None


class UserEvent(BaseModel):
    user_id: int
    username: Optional[str] = None
    email: Optional[str] = None
    action: str
    timestamp: datetime


class PaymentEvent(BaseModel):
    payment_id: int
    user_id: int
    amount: float
    status: str
    timestamp: datetime
    method_type: Optional[str] = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_envelope(event_type: str, payload: Dict[str, Any], event_id: str) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": event_type,
        "timestamp": now_utc().isoformat(),
        "payload": payload,
    }


# -------------------------
# Kafka 
# -------------------------
producer: Optional[Producer] = None

_stop_flag = threading.Event()
_consumer_thread: Optional[threading.Thread] = None


def _delivery_report(err, msg):
    if err is not None:
        logger.error("delivery_failed", extra={"error": str(err), "topic": msg.topic()})
    else:
        logger.info(
            "produced_message",
            extra={"topic": msg.topic(), "partition": msg.partition(), "offset": msg.offset()},
        )


def kafka_send(topic: str, message: Dict[str, Any]) -> Tuple[int, int]:
    if producer is None:
        raise RuntimeError("Kafka producer not initialized")

    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")

    # produce async + flush to get delivery
    producer.produce(topic, value=payload, on_delivery=_delivery_report)
    producer.flush(10)

    # confluent-kafka не возвращает partition/offset прямо из produce без callback.
    # Чтобы Postman/ответ были стабильными — вернём -1/-1 
    return -1, -1


def consumer_worker(topics: List[str]) -> None:
    conf = {
        "bootstrap.servers": KAFKA_BROKERS,
        "group.id": CONSUMER_GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }

    while not _stop_flag.is_set():
        try:
            consumer = Consumer(conf)
            consumer.subscribe(topics)
            logger.info("consumer_started", extra={"topics": topics, "group_id": CONSUMER_GROUP_ID})

            while not _stop_flag.is_set():
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("consumer_msg_error", extra={"error": str(msg.error())})
                    continue

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                except Exception:
                    value = msg.value().decode("utf-8", errors="replace")

                logger.info(
                    "event_processed",
                    extra={
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                        "value": value,
                    },
                )

            consumer.close()
        except KafkaException as e:
            logger.error("consumer_error", extra={"error": str(e)})
            time.sleep(2)
        except Exception as e:
            logger.error("consumer_unexpected_error", extra={"error": str(e)})
            time.sleep(2)


# -------------------------
# FastAPI 
# -------------------------
app = FastAPI(title="CinemaAbyss Events Service")


@app.on_event("startup")
def on_startup() -> None:
    global producer, _consumer_thread

    producer = Producer({"bootstrap.servers": KAFKA_BROKERS})

    _stop_flag.clear()
    _consumer_thread = threading.Thread(
        target=consumer_worker,
        args=([TOPIC_MOVIE, TOPIC_USER, TOPIC_PAYMENT],),
        daemon=True,
    )
    _consumer_thread.start()

    logger.info(
        "service_started",
        extra={"port": PORT, "kafka_brokers": KAFKA_BROKERS, "topics": [TOPIC_MOVIE, TOPIC_USER, TOPIC_PAYMENT]},
    )


@app.on_event("shutdown")
def on_shutdown() -> None:
    global producer

    _stop_flag.set()
    if _consumer_thread:
        _consumer_thread.join(timeout=5)

    if producer:
        producer.flush(5)
        producer = None


@app.get("/api/events/health")
def health():
    return {"status": True}


@app.post("/api/events/movie", status_code=201)
def create_movie_event(body: MovieEvent):
    try:
        event_id = f"movie-{body.movie_id}-{body.action}"
        envelope = make_envelope("movie", body.model_dump(), event_id)
        partition, offset = kafka_send(TOPIC_MOVIE, envelope)
        logger.info("movie_event_created", extra={"event_id": event_id, "topic": TOPIC_MOVIE})
        return {"status": "success", "partition": partition, "offset": offset, "event": envelope}
    except Exception as e:
        logger.exception("movie_event_failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to produce movie event")


@app.post("/api/events/user", status_code=201)
def create_user_event(body: UserEvent):
    try:
        event_id = f"user-{body.user_id}-{body.action}"
        envelope = make_envelope("user", body.model_dump(mode="json"), event_id)
        partition, offset = kafka_send(TOPIC_USER, envelope)
        logger.info("user_event_created", extra={"event_id": event_id, "topic": TOPIC_USER})
        return {"status": "success", "partition": partition, "offset": offset, "event": envelope}
    except Exception as e:
        logger.exception("user_event_failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to produce user event")


@app.post("/api/events/payment", status_code=201)
def create_payment_event(body: PaymentEvent):
    try:
        event_id = f"payment-{body.payment_id}-{body.status}"
        envelope = make_envelope("payment", body.model_dump(mode="json"), event_id)
        partition, offset = kafka_send(TOPIC_PAYMENT, envelope)
        logger.info("payment_event_created", extra={"event_id": event_id, "topic": TOPIC_PAYMENT})
        return {"status": "success", "partition": partition, "offset": offset, "event": envelope}
    except Exception as e:
        logger.exception("payment_event_failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to produce payment event")


@app.exception_handler(Exception)
def unhandled_exception_handler(_, exc: Exception):
    logger.exception("unhandled_exception", extra={"error": str(exc)})
    return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
