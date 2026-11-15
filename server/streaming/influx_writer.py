from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Event
import logging
import math
import time

from influxdb_client_3 import InfluxDBClient3, Point


logger = logging.getLogger(__name__)


class InfluxPublisher:
    def __init__(
        self,
        host: str,
        token: str,
        database: str,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        self.client = InfluxDBClient3(
            host=host,
            token=token,
            database=database,
        )

        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.queue = Queue()
        self.stop_event = Event()
        self.thread = None

        self.published = 0
        self.failed = 0

    @staticmethod
    def _to_point(output, sample):
        measurement = output.data_type.value
        point = Point(measurement)

        # Source tags: mux_number, cb37_pin, type, etc.
        source_tags = output.source.to_dict()

        for key, value in source_tags.items():
            if value is not None:
                point = point.tag(str(key), str(value))

        point = point.tag("data_type", measurement)

        value = float(sample.value)
        if not math.isfinite(value):
            raise ValueError(
                f"Cannot write non-finite sensor value: {value}"
            )

        point = point.field("value", value)

        timestamp = sample.time
        if isinstance(timestamp, datetime):
            point = point.time(timestamp)

        return point

    def publish_output(self, output):
        """
        Called by the acquisition thread.
        Queueing is quick; the database write occurs in the worker.
        """
        for sample in output.data:
            self.queue.put((output, sample))

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()

        self.thread = Thread(
            target=self._worker,
            daemon=True,
            name="influx-publisher",
        )
        self.thread.start()

    def _write_batch(self, batch):
        if not batch:
            return

        points = []

        for output, sample in batch:
            points.append(self._to_point(output, sample))

        try:
            self.client.write(record=points)
            self.published += len(points)

        except Exception:
            self.failed += len(points)
            logger.exception("InfluxDB batch write failed.")

    def _worker(self):
        batch = []
        last_flush = time.monotonic()

        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
                batch.append(item)
                self.queue.task_done()

            except Empty:
                pass

            elapsed = time.monotonic() - last_flush

            if (
                len(batch) >= self.batch_size
                or (batch and elapsed >= self.flush_interval)
            ):
                self._write_batch(batch)
                batch.clear()
                last_flush = time.monotonic()

        if batch:
            self._write_batch(batch)

    def close(self):
        self.stop_event.set()

        if self.thread:
            self.thread.join(timeout=10)

        self.client.close()


