import asyncio
import json
import statistics
import time
import uuid

import aio_pika
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

N = 1000
RUN_ID = uuid.uuid4().hex
PAYLOAD = "x" * 100


def make_body() -> bytes:
    return f"{RUN_ID}|{time.perf_counter()}|{PAYLOAD}".encode()


def parse(body: bytes):
    run_id, sent, _ = body.decode().split("|", 2)
    return run_id, float(sent)


async def bench_kafka():
    consumer = AIOKafkaConsumer(
        "benchmark",
        bootstrap_servers="localhost:9092",
        group_id=f"bench-{RUN_ID}",
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers="localhost:9092")
    await consumer.start()
    await producer.start()

    latencies = []

    async def reader():
        async for msg in consumer:
            run_id, sent = parse(msg.value)
            if run_id != RUN_ID:
                continue
            latencies.append(time.perf_counter() - sent)
            if len(latencies) == N:
                break

    reader_task = asyncio.create_task(reader())
    t0 = time.perf_counter()
    for _ in range(N):
        await producer.send_and_wait("benchmark", make_body())
    send_time = time.perf_counter() - t0
    await asyncio.wait_for(reader_task, timeout=60)
    total_time = time.perf_counter() - t0

    await producer.stop()
    await consumer.stop()
    return send_time, total_time, latencies


async def bench_rabbit():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    queue = await channel.declare_queue("benchmark", durable=True)
    await queue.purge()

    latencies = []
    done = asyncio.Event()

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process():
            _, sent = parse(message.body)
            latencies.append(time.perf_counter() - sent)
            if len(latencies) == N:
                done.set()

    await queue.consume(on_message)

    t0 = time.perf_counter()
    for _ in range(N):
        await channel.default_exchange.publish(
            aio_pika.Message(body=make_body(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="benchmark",
        )
    send_time = time.perf_counter() - t0
    await asyncio.wait_for(done.wait(), timeout=60)
    total_time = time.perf_counter() - t0

    await connection.close()
    return send_time, total_time, latencies


def report(name, send_time, total_time, latencies):
    ms = sorted(x * 1000 for x in latencies)
    p95 = ms[int(len(ms) * 0.95) - 1]
    print(f"{name:<10} | send: {send_time:6.2f} s | {N / send_time:7.0f} msg/s | "
          f"total: {total_time:6.2f} s | avg latency: {statistics.mean(ms):8.2f} ms | p95: {p95:8.2f} ms")


async def main():
    print(f"Messages: {N}, payload ~{len(PAYLOAD)} bytes, sequential publish with ack\n")
    report("Kafka", *await bench_kafka())
    report("RabbitMQ", *await bench_rabbit())


asyncio.run(main())