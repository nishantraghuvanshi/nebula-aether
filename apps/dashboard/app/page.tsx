"use client";
import React, { useState, useEffect } from 'react';

interface GpuState {
  gpu_temp: number;
  gpu_mem_used: number;
}

export default function Dashboard() {
  const [gpuState, setGpuState] = useState<GpuState>({ gpu_temp: 0, gpu_mem_used: 0 });
  const [connectionStatus, setConnectionStatus] = useState<string>('Connecting');
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
        setGpuState({
          gpu_temp: data.gpu_temp || 0,
          gpu_mem_used: data.gpu_mem_used || 0,
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
    <main style={{ fontFamily: 'monospace', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ color: '#333', marginBottom: '2rem' }}>Aether Dashboard</h1>
      
      <div style={{ marginBottom: '2rem' }}>
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

      <div style={{ 
        border: '2px solid #333', 
        padding: '2rem', 
        borderRadius: '8px',
        backgroundColor: '#f8f9fa'
      }}>
        <h2 style={{ marginTop: 0, color: '#333' }}>GPU-0 State</h2>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginTop: '1rem' }}>
          <div style={{ textAlign: 'center' }}>
            <p style={{ 
              fontSize: '2rem', 
              color: gpuState.gpu_temp > 80 ? '#dc3545' : gpuState.gpu_temp > 60 ? '#ffc107' : '#28a745',
              fontWeight: 'bold',
              margin: '0.5rem 0'
            }}>
              {gpuState.gpu_temp}°C
            </p>
            <p style={{ color: '#666', margin: 0 }}>Temperature</p>
          </div>
          
          <div style={{ textAlign: 'center' }}>
            <p style={{ 
              fontSize: '2rem', 
              color: gpuState.gpu_mem_used > 20000 ? '#dc3545' : gpuState.gpu_mem_used > 10000 ? '#ffc107' : '#28a745',
              fontWeight: 'bold',
              margin: '0.5rem 0'
            }}>
              {(gpuState.gpu_mem_used || 0).toLocaleString()} MB
            </p>
            <p style={{ color: '#666', margin: 0 }}>Memory Used</p>
          </div>
        </div>

        <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: '#e9ecef', borderRadius: '4px' }}>
          <h3 style={{ marginTop: 0, color: '#333' }}>System Status</h3>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>GPU Health:</strong> {
              gpuState.gpu_temp < 80 && gpuState.gpu_mem_used < 20000 ? '✅ Healthy' : '⚠️ Warning'
            }
          </p>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Last Update:</strong> {new Date().toLocaleTimeString()}
          </p>
        </div>
      </div>

      <div style={{ marginTop: '2rem', textAlign: 'center' }}>
        <p style={{ color: '#666', fontSize: '0.9rem' }}>
          Real-time GPU monitoring powered by Aether AI Control Plane
        </p>
      </div>
    </main>
  );
}
