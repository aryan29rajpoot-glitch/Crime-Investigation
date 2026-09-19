# FraudLens

### Digital Investigation & Artifact Correlation Platform

FraudLens is a prototype for analyzing and correlating digital investigation evidence such as **Call Detail Records (CDR), bank transactions, and chat evidence**.

It extracts entities, builds relationships between them, generates an investigation graph, and calculates a rule-based risk score.

## Features

- Multi-source evidence analysis
- Phone, UPI, bank account and IP extraction
- CDR and bank transaction parsing
- Evidence correlation
- Investigation relationship graph
- Risk scoring and risk levels
- Next.js investigation dashboard

## Tech Stack

**Frontend**
- Next.js
- React
- TypeScript
- CSS

**Backend**
- Python
- FastAPI
- Pandas
- Uvicorn

## Architecture

text
Evidence
   |
   +-- CDR
   +-- Bank Records
   +-- Chat Evidence
          |
          ↓
   Entity Extraction
          |
          ↓
   Evidence Correlation
          |
          ↓
   Investigation Graph
          |
          ↓
     Risk Analysis
          |
          ↓
    FraudLens Dashboard
Project Structure
Crime-Investigation/
├── backend/
│   ├── analysis/
│   ├── correlation/
│   ├── data/
│   ├── extraction/
│   ├── parsers/
│   └── main.py
│
├── frontend/
│   ├── app/
│   ├── public/
│   └── package.json
│
├── .gitignore
└── README.md
Example

FraudLens can correlate a transaction flow such as:

AC1001
   ↓ DEBIT ₹50,000
scammer@upi
   ↓ CREDIT ₹50,000
AC2001
   ↓ TRANSFER ₹45,000
mule@upi
   ↓ CREDIT ₹45,000
AC3001

Communication evidence can also be connected to these entities through relationships such as:

Phone → CALL → Phone
Phone → CHAT_LINK → UPI
Bank Account → DEBIT → UPI
UPI → CREDIT → Bank Account
Risk Analysis

The current prototype uses rule-based scoring based on:

Multiple transactions
Multiple entity connections
Rapid fund transfers

Example:

{
  "score": 75,
  "level": "HIGH",
  "reasons": [
    "Multiple transactions detected",
    "Entity has multiple connections",
    "Rapid fund transfer detected"
  ]
}
Run Locally
Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
Frontend

Open another terminal:

cd frontend
npm install
npm run dev

Frontend:

http://localhost:3000

Backend:

http://127.0.0.1:8000
Project Status

FraudLens is currently a prototype for educational, research, and demonstration purposes.

The risk score is a rule-based analytical indicator and should not be treated as a definitive determination of fraud or criminal activity.

Author

Aryan Rajpoot

B.Tech Computer Science & Engineering
Data Science Specialization
