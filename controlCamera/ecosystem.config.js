module.exports = {
  apps : [{
    name   : "backend-aflatoksin",
    script : "/home/ubuntu/Downloads/Aflatoksin-main/venv-backend/bin/uvicorn",
    args   : "main2:app --host 0.0.0.0 --port 3000",
    interpreter: "none", // Important: lets uvicorn manage the execution
    cwd    : "/home/ubuntu/Downloads/Aflatoksin-main/controlCamera", // REPLACE with your actual absolute path
    instances : 1,
    exec_mode : "fork",
    env: {
      PYTHONUNBUFFERED: "1" // Ensures logs show up immediately
    }
  }]
}