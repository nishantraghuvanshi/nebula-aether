"use client";
import React, { useState, useEffect } from 'react';

// Type definitions

export default function Dashboard() {
  const [state, setState] = useState<any>({ cluster_state: {}, carbon_intensity: 0, anomalies: {} });
  const [connectionStatus, setConnectionStatus] = useState('Connecting');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const ws = new WebSocket('ws://localhost:8080/graphql');

    ws.onopen = () => {
      setConnectionStatus('Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setState({
          cluster_state: data.cluster_state || {},
          carbon_intensity: data.carbon_intensity || 0,
          anomalies: data.anomalies || {},
        });
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      setConnectionStatus('Closed');
    };

    ws.onerror = () => {
      setConnectionStatus('Error');
    };

    return () => {
      ws.close();
    };
  }, []);

  if (!isClient) {
    return <div>Loading...</div>;
  }

  return (
    <main style={{ fontFamily: 'monospace', padding: '2rem', maxWidth: '1000px', margin: '0 auto' }}>
      <h1 style={{ color: 'white', marginBottom: '1rem' }}>Aether Dashboard</h1>

      <div style={{ marginBottom: '1rem' }}>
        <p style={{
          padding: '0.5rem 1rem',
          backgroundColor: connectionStatus === 'Connected' ? '#d4edda' : '#f8d7da',
          color: connectionStatus === 'Connected' ? '#155724' : '#721c24',
          borderRadius: '4px',
          display: 'inline-block'
        }}>
          Connection Status: {connectionStatus}
        </p>
      </div>

      <p>Carbon Intensity: {state.carbon_intensity.toFixed(0)} gCO2/kWh</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
        {Object.keys(state.cluster_state).length === 0 ? (
          <div style={{ border: '1px solid #ccc', padding: '2rem', borderRadius: '8px', background: '#f8f9fa', textAlign: 'center', color :'black' }}>
            <p>No GPU data available. Waiting for telemetry...</p>
            <p style={{ color: '#666', fontSize: '0.9rem' }}>
              Make sure the Rust agent is running and publishing data.
            </p>
          </div>
        ) : (
          Object.entries(state.cluster_state).map(([gpuId, gpuState]) => (
            <div key={gpuId} style={{ border: state.anomalies[gpuId] ? '2px solid red' : '1px solid #333', padding: '1rem', borderRadius: '8px', background: '#f8f9fa',color: 'black' }}>
              <h2 style={{ marginTop: 0 }}>{gpuId.toUpperCase()}</h2>
              <p>Temperature: {(gpuState as any).gpu_temp || 0}°C</p>
              <p>Memory Used: {((gpuState as any).gpu_mem_used || 0).toLocaleString()} MB</p>
              <p>Utilization: {(gpuState as any).utilization_gpu || 0}%</p>
              <p>Power: {(gpuState as any).power_draw_w || 0}W</p>
              {state.anomalies[gpuId] && <p style={{ color: 'red' }}>ANOMALY DETECTED</p>}
            </div>
          ))
        )}
      </div>

      <div style={{ marginTop: '2rem', textAlign: 'center' }}>
        <p style={{ color: '#666', fontSize: '0.9rem' }}>
          Real-time GPU monitoring powered by Aether AI Control Plane
        </p>
      </div>
    </main>
  );
}
