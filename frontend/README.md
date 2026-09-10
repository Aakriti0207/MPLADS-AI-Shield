# MPLADS AI Shield

## Overview

MPLADS AI Shield is a web-based project monitoring and analytics system designed to monitor MPLADS projects, identify potential risks and anomalies, and provide useful insights through dashboards, alerts, analytics, maps, and reports.

The system combines a React.js frontend, FastAPI backend, PostgreSQL database, and machine learning modules for project analysis and risk assessment.
### Frontend

Open another PowerShell window and navigate to the frontend folder:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Frontend will run at:

```text
http://localhost:5173/
```

## Features

* Project Monitoring
* User Login & Authentication
* Dashboard & Statistics
* Project Listing
* Project Details
* Alerts & Notifications
* Analytics
* Project Map
* Reports
* Risk Analysis
* Anomaly Detection
* Duplicate Project Analysis
* Compliance Analysis
* ML-based Risk Scoring
* Responsive User Interface

## Tech Stack

### Frontend

* React.js
* Vite
* JavaScript
* Tailwind CSS
* HTML5
* CSS3

### Backend

* Python
* FastAPI
* SQLAlchemy
* JWT Authentication

### Database

* PostgreSQL

### Machine Learning

* Data Preprocessing
* Feature Engineering
* Compliance Analysis
* Anomaly Detection
* Duplicate Analysis
* Risk Scoring

## Project Structure

```text
MPLADS-AI-Shield/
├── backend/
│   ├── app/
│   ├── ml/
│   ├── tests/
│   ├── create_tables.py
│   ├── seed_data.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── App.jsx
│   │   ├── data.js
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── docs/
└── README.md
````

## Machine Learning Pipeline

The project includes multiple ML and analytical phases for processing and evaluating project data.

* Data Inventory
* Data Preprocessing
* Canonical Data Preparation
* Feature Engineering
* Compliance Analysis
* Anomaly Detection
* Duplicate Detection
* Risk Scoring

The ML pipeline is designed to generate risk-related information that can be used by the backend and frontend for project monitoring and prioritization.

## Current Status

**Integrated Application Development — In Progress**

The React.js frontend, FastAPI backend, and PostgreSQL database have been integrated successfully.

The major project monitoring modules, authentication, dashboard, projects, alerts, analytics, maps, and reports have been implemented.

The ML pipeline and final risk-scoring workflow are currently being integrated and validated with the project database and frontend.

## Future Development

* Advanced Risk Prediction
* Improved Anomaly Detection
* Automated Project Prioritization
* Historical Risk Analysis
* Automated Report Generation
* Advanced Analytics
* Production Deployment

## Project Goal

The main goal of MPLADS AI Shield is to provide an intelligent monitoring system that helps identify suspicious project patterns, assess project risks, and support transparent and data-driven monitoring of MPLADS projects.

```
```
