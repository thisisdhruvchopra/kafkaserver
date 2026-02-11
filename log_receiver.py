#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from kafka import KafkaConsumer


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_fernet(config):
    key = config.get("encryption_key", "").strip()
    if not key:
        raise ValueError("encryption_key is required in config")
    return Fernet(key.encode("utf-8"))


def build_consumer(config):
    kafka_cfg = config.get("kafka", {})
    return KafkaConsumer(
        *config.get("topics", []),
        bootstrap_servers=kafka_cfg.get("bootstrap_servers", ["localhost:9092"]),
        security_protocol=kafka_cfg.get("security_protocol", "PLAINTEXT"),
        group_id=kafka_cfg.get("group_id", "log_receiver"),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: m,
    )


def decrypt_message(fernet, kafka_message):
    try:
        data = fernet.decrypt(kafka_message.value)
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Failed to decrypt message: {e}", file=sys.stderr)
        return None


def get_log_file_path(output_dir, topic, rotation_mb):
    topic_dir = Path(output_dir) / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    
    # Find current log file or create new one
    date_str = datetime.now().strftime("%Y%m%d")
    index = 1
    
    while True:
        log_file = topic_dir / f"{date_str}_{index:03d}.jsonl"
        if not log_file.exists():
            return log_file
        
        # Check file size
        size_mb = log_file.stat().st_size / (1024 * 1024)
        if size_mb < rotation_mb:
            return log_file
        
        index += 1


def write_log(output_dir, topic, payload, rotation_mb):
    log_file = get_log_file_path(output_dir, topic, rotation_mb)
    
    with open(log_file, "a", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Chatterbox Log Receiver - decrypts and saves Kafka logs"
    )
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument(
        "--verbose", action="store_true", help="Print received messages to console"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    fernet = get_fernet(config)
    consumer = build_consumer(config)
    
    output_dir = config.get("output_dir", "/var/log/chatterbox-logs")
    rotation_mb = config.get("file_rotation_mb", 100)
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] Log receiver started")
    print(f"[INFO] Listening to {len(config.get('topics', []))} topics")
    print(f"[INFO] Output directory: {output_dir}")
    print(f"[INFO] File rotation: {rotation_mb} MB")
    print(f"[INFO] Waiting for messages...")
    
    message_count = 0
    
    try:
        for message in consumer:
            payload = decrypt_message(fernet, message)
            if payload is None:
                continue
            
            message_count += 1
            topic = message.topic
            
            # Add Kafka metadata
            payload["_kafka_topic"] = topic
            payload["_kafka_partition"] = message.partition
            payload["_kafka_offset"] = message.offset
            payload["_received_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Write to disk
            write_log(output_dir, topic, payload, rotation_mb)
            
            if args.verbose:
                msg_type = payload.get("type", "unknown")
                host = payload.get("host", "unknown")
                print(f"[{message_count}] {topic} | {msg_type} | {host}")
            
            if message_count % 100 == 0:
                print(f"[INFO] Processed {message_count} messages")
    
    except KeyboardInterrupt:
        print(f"\n[INFO] Shutting down... Processed {message_count} total messages")
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
