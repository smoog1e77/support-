#!/usr/bin/env bash
# Запуск бота: создаёт venv при первом старте, ставит зависимости и запускает.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "→ Создаю виртуальное окружение..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "→ Устанавливаю зависимости..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "→ Запускаю бота (Ctrl+C для остановки)..."
python bot.py
