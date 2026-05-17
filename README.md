# LiquidityAI — Предиктивное управление ликвидностью

> FinTech Hackathon 2026 | Treasury Intelligence Platform

## Запуск

```bat
start.bat
```

Или вручную:

```powershell
.venv\Scripts\python.exe -W ignore -m streamlit run dashboard/app.py --theme.base dark
```

Открыть: **http://localhost:8501**

---

## Архитектура

```
fintech-liquidity/
├── data/
│   └── generator.py        # Генератор синтетических данных (12 мес., 6 ностро-счетов)
├── models/
│   ├── forecaster.py       # ML: Random Forest + GBM прогноз cash flow (72ч)
│   ├── alert_system.py     # Predictive alert engine (4 уровня severity)
│   ├── optimizer.py        # Greedy оптимизатор перераспределения ликвидности
│   └── stress_tester.py    # 6 стресс-сценариев (SWIFT, SEPA, валюты, пики)
├── api/
│   └── main.py             # FastAPI REST API (/api/accounts, /forecast, /alerts, ...)
├── dashboard/
│   └── app.py              # Streamlit дашборд (6 вкладок)
├── requirements.txt
└── start.bat
```

---

## Что умеет система

### ML-прогнозирование (Random Forest + Gradient Boosting)
- Предсказывает входящие/исходящие потоки и баланс на 1–7 дней
- Фичи: день недели, день месяца, лаги (1/2/3/7/14 дн.), rolling mean, баланс
- Учитывает задержки клиринга: SEPA (1д), SWIFT (3д), Card (5д), Local (0д)
- Отображает доверительный интервал через дисперсию деревьев леса

### Предиктивные алерты
| Тип | Описание |
|---|---|
| `CURRENT_DEFICIT` | Баланс уже ниже минимума — немедленно |
| `FORECAST_DEFICIT` | Прогнозируемый дефицит через N дней |
| `CLEARING_RISK` | Высокая зависимость от ожидаемых клиринговых поступлений |
| `EXCESS_IDLE` | Избыточные средства не приносят доход |

Severity: **CRITICAL / HIGH / MEDIUM / LOW**

### Оптимизатор ликвидности
- Находит профицитные и дефицитные счета
- Рекомендует переводы с учётом: стоимости (bps), времени перевода, FX-конвертации
- Считает упущенный доход на idle-капитале (при ставке 4.5% годовых)

### Стресс-тестирование (6 сценариев)
| Сценарий | Описание |
|---|---|
| SWIFT Delay | +2 дня задержки SWIFT-переводов |
| EU Holiday | SEPA не работает 2 дня |
| Volume Spike | +80% объём транзакций |
| Card Delay | +3 дня задержки карточного клиринга |
| FX Shock | EUR −8%, GBP −5% |
| Multi Crisis | Всё сразу — наихудший сценарий |

### Дашборд (6 вкладок)
1. **Обзор** — KPI карточки, распределение по счетам, 90-дневный тренд
2. **Счета** — детали по каждому, gauge-chart, история 30 дней
3. **Прогноз cash flow** — факт + прогноз + CI, breakdown инфлоу/аутфлоу
4. **Алерты** — все активные с деталями и рекомендациями
5. **Оптимизация** — idle-капитал, конкретные рекомендации переводов
6. **Стресс-тест** — интерактивный симулятор, сравнительный chart, impact table

### REST API (FastAPI)
```
GET  /api/accounts          — текущие балансы
GET  /api/forecast?days=3   — прогноз cash flow
GET  /api/alerts            — активные алерты
GET  /api/recommendations   — рекомендации оптимизации
GET  /api/scenarios         — список стресс-сценариев
POST /api/stress-test       — запуск стресс-теста
GET  /api/dashboard         — все данные одним запросом
```

Запуск API:
```powershell
.venv\Scripts\python.exe run_api.py
# http://localhost:8000/docs
```

---

## Данные

6 ностро-счетов в 3 валютах:

| Счёт | Валюта | Система | Мин. баланс | Целевой |
|---|---|---|---|---|
| Citibank USD | USD | SWIFT | $500K | $2M |
| Stripe USD | USD | CARD | $300K | $1.5M |
| Deutsche Bank EUR | EUR | SEPA | €400K | €1.8M |
| Adyen EUR | EUR | CARD | €250K | €1.2M |
| Barclays GBP | GBP | LOCAL | £200K | £800K |
| HSBC GBP | GBP | SWIFT | £150K | £600K |

Генерируется 12 месяцев истории с реалистичными паттернами:
- Эффект дня недели (пн: +20%, пт: −15%)
- Эффект месяца (дек: +35%, янв: −20%)
- Эффект зарплатного периода (25–31 число: +50%)
- Банковские праздники (SEPA/LOCAL не работают)
- Задержки клиринга по типу платёжной системы
