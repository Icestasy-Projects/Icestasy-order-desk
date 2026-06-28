# Icestasy Order Desk — launch script
# Run from the icestasy-order-desk folder: .\run.ps1

$env:SUPABASE_URL         = "https://acngdpcpxburkzqxjpbf.supabase.co"
$env:SUPABASE_KEY         = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3OTg4MjcsImV4cCI6MjA5NzM3NDgyN30.t2XuMvFL5iyGeWkERJrTFPmJdNMb48gCUcn8Z0j5bsM"
$env:SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTc5ODgyNywiZXhwIjoyMDk3Mzc0ODI3fQ.dZHfewnIMa8GV4aPMYXKdOPGSWz00g33u3_QDCjAC2g"

Write-Host "Starting Icestasy Order Desk on http://localhost:5001" -ForegroundColor Green
python app.py
