# Kafka Server + Log Receiver

This folder contains the Kafka broker and log receiver for the Chatterbox honeypot system.

**Run this on your separate Kafka VM.**

## Components

1. **Kafka Broker** (Docker): Message bus for chat and logs
2. **Log Receiver** (Python): Decrypts and saves all logs to disk

---

## Setup

### Prerequisites

- Ubuntu/Debian Linux
- Docker + Docker Compose installed
- Python 3.10+

### 1. Install Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# Log out and back in for group changes
```

### 2. Configure Kafka

Edit `docker-compose.yml`:
- Replace `KAFKA_VM_IP` with this VM's actual IP address (not localhost)
- This IP must be reachable from your Dev/Prof VMs

Example:
```yaml
- KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://192.168.1.100:9092
```

### 3. Start Kafka

```bash
cd /path/to/kafka-server
docker-compose up -d
```

Verify:
```bash
docker ps
docker logs kafka
```

Wait ~30 seconds for Kafka to fully start.

### 4. Configure Log Receiver

Edit `config.json`:
- Paste the **same Fernet encryption key** from your Dev/Prof VMs
- Optionally change `output_dir` (default: `/var/log/chatterbox-logs`)

### 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 6. Test Log Receiver (foreground)

```bash
python log_receiver.py --config config.json --verbose
```

You should see:
```
[INFO] Log receiver started
[INFO] Listening to 17 topics
[INFO] Output directory: /var/log/chatterbox-logs
[INFO] Waiting for messages...
```

Leave this running and start the Dev VM clients. You should see messages arriving.

### 7. Run Log Receiver as a Service

Create `/etc/systemd/system/chatterbox-receiver.service`:

```ini
[Unit]
Description=Chatterbox Log Receiver
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/kafka-server
ExecStart=/usr/bin/python3 /path/to/kafka-server/log_receiver.py --config /path/to/kafka-server/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable chatterbox-receiver
sudo systemctl start chatterbox-receiver
sudo systemctl status chatterbox-receiver
```

View logs:
```bash
sudo journalctl -u chatterbox-receiver -f
```

---

## Log Output Structure

Logs are saved to `output_dir` (default `/var/log/chatterbox-logs/`):

```
/var/log/chatterbox-logs/
├── chat_topic/
│   ├── 20260211_001.jsonl
│   └── 20260211_002.jsonl
├── syslog-message/
│   └── 20260211_001.jsonl
├── authlog-message/
│   └── 20260211_001.jsonl
├── wndsystemdsecurity/
│   └── 20260211_001.jsonl
...
```

Each file is JSONL (one JSON object per line). Files rotate at 100 MB by default.

---

## Viewing Logs

**Quick peek:**
```bash
tail -f /var/log/chatterbox-logs/syslog-message/*.jsonl | jq .
```

**Count messages per topic:**
```bash
for dir in /var/log/chatterbox-logs/*/; do
  echo "$(basename $dir): $(cat $dir/*.jsonl 2>/dev/null | wc -l) messages"
done
```

**Search for specific host:**
```bash
grep '"host": "dev-1"' /var/log/chatterbox-logs/*/*.jsonl | jq .
```

---

## Troubleshooting

**Kafka won't start:**
- Check Docker logs: `docker logs kafka`
- Verify port 9092 is not in use: `sudo netstat -tlnp | grep 9092`

**Log receiver can't connect:**
- Verify Kafka is running: `docker ps`
- Test connection: `telnet localhost 9092`
- Check `bootstrap_servers` in config.json

**No messages arriving:**
- Verify Dev/Prof VMs have correct Kafka IP in their configs
- Check firewall: `sudo ufw status`
- Allow port 9092: `sudo ufw allow 9092/tcp`

**Decryption fails:**
- Ensure encryption_key is identical across all VMs
- Check log receiver output for "Failed to decrypt" errors

---

## Stopping Services

```bash
# Stop log receiver
sudo systemctl stop chatterbox-receiver

# Stop Kafka
docker-compose down

# Remove all Kafka data (CAUTION)
docker-compose down -v
```

---

## Security Notes

This is a honeypot/research environment with intentionally simplified security:
- PLAINTEXT protocol (no TLS)
- No authentication
- Auto-create topics enabled
- Keep this VM isolated on your LAN
- Do NOT expose port 9092 to the internet
