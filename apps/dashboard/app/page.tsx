"use client";
import React, { useState, useEffect } from 'react';

// Type definitions

export default function Dashboard() {
  const [state, setState] = useState<any>({ cluster_state: {}, carbon_intensity: 0, anomalies: {} });
  const [connectionStatus, setConnectionStatus] = useState('Connecting');
  const [isClient, setIsClient] = useState(false);
  const [jobForm, setJobForm] = useState({ id: '', type: 'training' });
  const [submitStatus, setSubmitStatus] = useState('');

  const submitJob = async (e: any) => {
    e.preventDefault();
    setSubmitStatus('Submitting...');
    
    try {
      const response = await fetch('http://localhost:8080/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(jobForm),
      });
      
      if (response.ok) {
        setSubmitStatus('Job submitted successfully!');
        setJobForm({ id: '', type: 'training' });
        setTimeout(() => setSubmitStatus(''), 3000);
      } else {
        const error = await response.text();
        setSubmitStatus(`Error: ${error}`);
        setTimeout(() => setSubmitStatus(''), 5000);
      }
    } catch (error) {
      setSubmitStatus(`Error: ${error}`);
      setTimeout(() => setSubmitStatus(''), 5000);
    }
  };

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

      {/* Job Submission Form */}
      <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f9f9f9' }}>
        <h3 style={{ marginTop: 0, color: '#333' }}>Submit GPU Job</h3>
        <form onSubmit={submitJob} style={{ display: 'flex', gap: '1rem', alignItems: 'end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#333' }}>Job ID:</label>
            <input
              type="text"
              value={jobForm.id}
              onChange={(e) => setJobForm({ ...jobForm, id: e.target.value })}
              placeholder="e.g., training-job-001"
              required
              style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', minWidth: '200px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#333' }}>Job Type:</label>
            <select
              value={jobForm.type}
              onChange={(e) => setJobForm({ ...jobForm, type: e.target.value })}
              style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
            >
              <option value="training">Training</option>
              <option value="inference">Inference</option>
            </select>
          </div>
          <button
            type="submit"
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Submit Job
          </button>
        </form>
        {submitStatus && (
          <p style={{ 
            marginTop: '1rem', 
            padding: '0.5rem', 
            backgroundColor: submitStatus.includes('Error') ? '#f8d7da' : '#d4edda',
            color: submitStatus.includes('Error') ? '#721c24' : '#155724',
            borderRadius: '4px'
          }}>
            {submitStatus}
          </p>
        )}
      </div>

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
