# MPLADS AI Shield Frontend

## Overview

The MPLADS AI Shield frontend is a web-based monitoring and analytics interface for managing and monitoring MPLADS projects, including project progress, alerts, analytics, maps, reports, and risk information.

The frontend is developed using React.js and Vite and is integrated with the FastAPI backend and PostgreSQL database.

## Run Locally

```bash
npm install
npm run dev
```

Open:

http://localhost:5173/

Make sure the FastAPI backend is running before accessing live project data.

## Implemented Features

* 🏠 Home Page
* 🔐 Login & Authentication
* 📊 Monitoring Dashboard
* 📁 Projects Listing
* 📋 Project Details
* 🚨 Alerts & Notifications
* 📈 Analytics Dashboard
* 🗺️ Project Map
* 📑 Reports
* 📱 Responsive UI
* 🔗 FastAPI Backend Integration
* 🗄️ PostgreSQL Database Integration
* 🤖 ML-based Risk & Anomaly Analysis

## Tech Stack

Frontend

* React.js
* Vite
* JavaScript
* Tailwind CSS
* HTML5
* CSS3

Backend

* Python
* FastAPI
* SQLAlchemy
* JWT Authentication

Database

* PostgreSQL

  Machine Learning

* Data Preprocessing
* Feature Engineering
* Compliance Analysis
* Anomaly Detection
* Duplicate Analysis
* Risk Scoring





## Project Structure

```text
frontend/
├── src/
│   ├── components/
│   │   ├── Layout.jsx
│   │   └── UI.jsx
│   │
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Projects.jsx
│   │   ├── ProjectDetails.jsx
│   │   ├── Alerts.jsx
│   │   ├── Analytics.jsx
│   │   ├── MapPage.jsx
│   │   └── Reports.jsx
│   │
│   ├── App.jsx
│   ├── data.js
│   ├── index.css
│   └── main.jsx
│
├── package.json
├── package-lock.json
├── vite.config.js
├── tailwind.config.js
└── index.html
```

## Current Project Milestone

##Current Status

**Integrated Application Development — In Progress 🚧**

The frontend, FastAPI backend, and PostgreSQL database have been integrated successfully. Major monitoring, analytics, alerts, project, map, and report modules are implemented.

The ML pipeline is currently being connected with the final project risk-scoring workflow so that risk scores and risk levels are reflected consistently in the database and frontend.

## Future Development

* Advanced risk prediction
* Improved anomaly detection
* Automated project prioritization
* Historical risk analysis
* Automated report generation
* Production deployment
