# SmallWorld Backend Engineer Technical Assessment

A Django-based implementation and written solution for the SmallWorld Backend Engineer technical assessment.

---

## Project Overview

This repository contains the written answers and coding implementation for the SmallWorld Backend Engineer technical assessment.

The assessment consists of:

* **Section 1 — Debug This:** production debugging scenarios
* **Section 2 — Real Decisions:** backend architecture and engineering decisions
* **Section 3 — Write It:** a Django management command

The implementation focuses on correctness, maintainability, production considerations, and clear Django conventions.

---

## Project Structure

```text
smallworld-backend-assessment/
│
├── manage.py
├── README.md
├── answers.md
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
└── rewards/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    │
    ├── migrations/
    │   ├── __init__.py
    │   └── 0001_initial.py
    │
    └── management/
        ├── __init__.py
        └── commands/
            ├── __init__.py
            ├── audit_stale_rewards.py
            └── seed_rewards.py
```

The written solutions for Q1–Q7 are contained in [`answers.md`](answers.md).

The Q8 implementation is located at:

```text
rewards/management/commands/audit_stale_rewards.py
```

A small seed command is included to make the assessment easy to test:

```text
rewards/management/commands/seed_rewards.py
```

---

# Setup

## 1. Clone the repository

```bash
git clone <repository-url>
cd smallworld-backend-assessment
```

## 2. Create a virtual environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Run migrations

```bash
python manage.py makemigrations rewards
```

## 4. Apply migrations

```bash
python manage.py migrate
```



### Apply changes

```bash
python manage.py audit_stale_rewards --fix
```

Example:

```text
Found 3 stale reward(s).
cash: 2
voucher: 1
Expired 3 stale reward(s).
```

Individual expired reward IDs are also written to the Python application logger at INFO level.

---

# Testing Q8

A seed command is included so the management command can be tested without manually creating database records.

## 1. Seed sample data

```bash
python manage.py seed_rewards
```


## 2. Run the dry run

```bash
python manage.py audit_stale_rewards
```

Expected output:

```text
Found 3 stale reward(s).
cash: 2
voucher: 1
```

At this point, no records should have been modified.

## 3. Apply the fix

```bash
python manage.py audit_stale_rewards --fix
```

---