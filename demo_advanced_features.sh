#!/bin/bash

echo "🚀 Aether Advanced Features Demo"
echo "================================"
echo ""

echo "1. 🧠 Testing Anomaly Detection..."
echo "   - Normal values (should be OK):"
curl -s http://localhost:8000/anomaly -X POST -H "Content-Type: application/json" -d '{"gpu_temp": 45, "gpu_mem_used": 1000}' | jq .
echo ""

echo "   - Anomalous values (should detect anomaly):"
curl -s http://localhost:8000/anomaly -X POST -H "Content-Type: application/json" -d '{"gpu_temp": 99, "gpu_mem_used": 25000}' | jq .
echo ""

echo "2. 🌱 Testing Carbon Awareness..."
echo "   - Training job with high carbon intensity (should be denied):"
curl -s http://localhost:8000/predict -X POST -H "Content-Type: application/json" -d '{"gpu_temp": 45, "gpu_mem_used": 1000, "job_type": "training", "carbon_intensity": 500}' | jq .
echo ""

echo "   - Training job with normal carbon intensity (should be approved):"
curl -s http://localhost:8000/predict -X POST -H "Content-Type: application/json" -d '{"gpu_temp": 45, "gpu_mem_used": 1000, "job_type": "training", "carbon_intensity": 300}' | jq .
echo ""

echo "   - Inference job with high carbon intensity (should be approved - lighter workload):"
curl -s http://localhost:8000/predict -X POST -H "Content-Type: application/json" -d '{"gpu_temp": 45, "gpu_mem_used": 1000, "job_type": "inference", "carbon_intensity": 500}' | jq .
echo ""

echo "3. ⚡ Testing Predictive Power-Gating..."
echo "   - Submitting a job to trigger scheduling:"
curl -s http://localhost:8080/submit -X POST -H "Content-Type: application/json" -d '{"id": "demo-job", "type": "inference"}' | jq .
echo ""

echo "   - Waiting for job processing and power-gating to trigger..."
sleep 10

echo "   - The orchestrator should have sent a sleep command to the agent when the queue was empty"
echo "   - Check the agent logs for sleep/wake messages"
echo ""

echo "4. 📊 Dashboard Status..."
echo "   - Dashboard should be running at: http://localhost:3000"
echo "   - WebSocket connection should show real-time GPU telemetry"
echo ""

echo "✅ All advanced features have been demonstrated!"
echo ""
echo "🎯 Summary of Advanced Features:"
echo "   • Zero-touch anomaly detection using IsolationForest"
echo "   • Carbon-aware scheduling based on grid intensity"
echo "   • Predictive power-gating with sleep mode"
echo "   • Real-time dashboard with WebSocket streaming"
echo ""
echo "🌟 Aether is now a truly intelligent GPU control plane!"

