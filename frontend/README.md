# MPLADS AI Shield Frontend

## Overview

The MPLADS AI Shield frontend is a web-based monitoring and analytics interface designed to provide a centralized view of MPLADS projects, their progress, alerts, reports, and analytics.

## Run Locally

```bash
npm install
npm run dev
```

Open the local development URL provided by Vite, typically:

```text
http://localhost:5173/
```

## Implemented Features

* 🏠 Home Page
* 🔐 Login Page
* 📊 Monitoring Dashboard
* 📁 Projects Listing
* 📋 Project Details
* 🚨 Alerts & Notifications
* 📈 Analytics Dashboard
* 🗺️ Project Map View
* 📑 Reports
* 📱 Responsive UI
* 🧩 Reusable UI Components
* 📊 Mock Data for Frontend Demonstration

## Current Status

The frontend UI, navigation, reusable components, and major application pages have been implemented using mock data.

Backend integration and additional intelligent monitoring capabilities will be developed as part of the next stages of the project.

## Tech Stack

* React.js
* Vite
* JavaScript
* Tailwind CSS
* HTML5
* CSS3

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

## Future Development

* Backend integration with the project's selected backend technology
* REST API integration
* Real project data integration
* Database integration
* Authentication and authorization
* Advanced monitoring and analytics
* AI-based project risk and anomaly detection
* Intelligent alerts and project prioritization

## Current Project Milestone

**Frontend Prototype — Completed ✅**

The major frontend screens, navigation, and reusable UI components have been implemented and are currently demonstrated using mock data.
