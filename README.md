# RideShield 🏍️🛡️

RideShield is an end-to-end telematics and active protection platform. It captures real-time sensor data (GPS, Accelerometer, Gyroscope) from a rider's mobile device, processes incidents (like high G-force crashes) on a robust backend, and allows insurers to monitor rider metrics via a dedicated web dashboard.

---

## 🏗️ Project Structure

The repository is divided into three main components:
1. **`backend/`**: A FastAPI Python server handling real-time telemetry ingestion, Postgres database interactions, and Redis queue processing.
2. **`rider-app/`**: An Expo (React Native) mobile application that tracks live telemetry data using mobile hardware sensors.
3. **`insurer-dashboard/frontend-web/`**: A React web dashboard for insurance providers to monitor active shifts, review claims, and view incident telemetry.

---

## 🚀 Getting Started

Follow the steps below to spin up the entire ecosystem on your local machine. You will need **four separate terminal windows** running concurrently.

### 1. Setup & Run the Backend (Terminals 1 & 2)
The backend uses Python and requires a virtual environment. It also runs a main API server and a separate Redis worker for processing telemetry queues.

**Terminal 1: Start the API Server**
```bash
cd backend
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate
# Activate virtual environment (Mac/Linux)
# source venv/bin/activate

pip install -r requirements.txt

# Start the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Start the Telemetry Worker**
```bash
cd backend
# Activate virtual environment (Windows)
.\venv\Scripts\activate

# Run the Redis queue worker
python -u redis\workers\telemetry_worker.py
```

### 2. Setup & Run the Rider App (Terminal 3)
The Rider App is built with Expo. You can run it on a physical device using Expo Go, or on a local emulator.

**Terminal 3: Start Expo**
```bash
cd rider-app
npm install

# Start the Expo development server (clear cache to prevent stale builds)
npx expo start --clear
```
*Tip: Scan the QR code with the Expo Go app on your phone to test real hardware sensors (Gyroscope & Accelerometer).*

### 3. Setup & Run the Insurer Dashboard (Terminal 4)
The web dashboard provides live visibility into rider shifts and safety scores.

**Terminal 4: Start Web Dashboard**
```bash
cd insurer-dashboard/frontend-web
npm install

# Start the development server
npm run dev
```
*The dashboard will typically be available at http://localhost:5173 or the port specified in the terminal output.*

---

## 🛠️ Prerequisites
- **Node.js**: v18+ recommended (for `rider-app` and `insurer-dashboard`).
- **Python**: v3.10+ recommended (for `backend`).
- **PostgreSQL**: Ensure you have a running Postgres instance configured in your `.env`.
- **Redis**: Required for the telemetry queue worker. 

*Enjoy building with RideShield!*
