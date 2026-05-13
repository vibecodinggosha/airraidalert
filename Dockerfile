FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Telethon session file is expected at /app/sessions/airraidalert.session
# Mount a volume there to persist auth across restarts
ENV SESSION_NAME=/app/sessions/airraidalert

CMD ["python", "bot.py"]
