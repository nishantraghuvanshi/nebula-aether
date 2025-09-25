"use client";
import React, { useState, useEffect } from 'react';

// Type definitions

export default function Dashboard() {
  const [state, setState] = useState<any>({ cluster_state: {}, carbon_intensity: 0, anomalies: {} });
  const [connectionStatus, setConnectionStatus] = useState('Connecting');
  const [isClient, setIsClient] = useState(false);
  const [jobForm, setJobForm] = useState({ id: 'neural-network-training' });
  const [submitStatus, setSubmitStatus] = useState('');
  const [jobStatus, setJobStatus] = useState<any>({});
  const [jobQueue, setJobQueue] = useState<any[]>([]);
  const [completedJobs, setCompletedJobs] = useState<any[]>([]);

  // Available job definitions
  const availableJobs = [
    { id: 'neural-network-training', name: 'Neural Network Training', type: 'training' },
    { id: 'matrix-multiply-heavy', name: 'Matrix Multiplication Benchmark', type: 'compute' },
    { id: 'image-inference-batch', name: 'Image Inference Simulation', type: 'inference' },
    { id: 'monte-carlo-simulation', name: 'Monte Carlo Pi Estimation', type: 'simulation' },
    { id: 'video-encoding-benchmark', name: 'Video Encoding Benchmark', type: 'encoding' },
    { id: 'ray-tracing-benchmark', name: 'Ray Tracing Benchmark', type: 'rendering' },
    { id: 'protein-folding-simulation', name: 'Protein Folding Simulation', type: 'scientific' },
    { id: 'llm-finetuning-simulation', name: 'LLM Fine-tuning Simulation', type: 'llm' },
    { id: 'memory-stress-test', name: 'Memory Stress Test', type: 'memory' },
    { id: 'simple-cpu-test', name: 'Simple CPU Test', type: 'test' }
  ];

  const submitJob = async (e: React.FormEvent<HTMLFormElement>) => {
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

  const killJob = async (jobId: string) => {
    try {
      const response = await fetch(`http://localhost:8080/kill/${jobId}`, {
        method: 'POST',
      });

      if (response.ok) {
        setSubmitStatus(`Job ${jobId} killed successfully!`);
        setTimeout(() => setSubmitStatus(''), 3000);
      } else {
        const error = await response.text();
        setSubmitStatus(`Error killing job: ${error}`);
        setTimeout(() => setSubmitStatus(''), 5000);
      }
    } catch (error) {
      setSubmitStatus(`Error killing job: ${error}`);
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

        // Update job status if available
        if (data.job_status) {
          setJobStatus(data.job_status);
        }

        // Update job queue if available
        if (data.job_queue) {
          setJobQueue(data.job_queue);
        }

        // Update completed jobs if available
        if (data.completed_jobs) {
          setCompletedJobs(data.completed_jobs);
        }
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
            <label style={{ display: 'block', marginBottom: '0.5rem', color: '#333' }}>Select Job:</label>
            <select
              value={jobForm.id}
              onChange={(e) => setJobForm({ id: e.target.value })}
              style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', minWidth: '250px' }}
            >
              {availableJobs.map(job => (
                <option key={job.id} value={job.id}>
                  {job.name} ({job.type})
                </option>
              ))}
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

      {/* Job Pipeline Display */}
      <div style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>

        {/* Job Queue */}
        <div style={{ padding: '1rem', border: '1px solid #6c757d', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3 style={{ marginTop: 0, color: '#333', textAlign: 'center' }}>📋 Job Queue</h3>
          <div style={{ fontSize: '0.9rem', color: '#666', textAlign: 'center', marginBottom: '1rem' }}>
            {jobQueue.length} pending {jobQueue.length > 5 && '(showing first 5)'}
          </div>
          {jobQueue.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontStyle: 'italic' }}>No jobs queued</div>
          ) : (
            jobQueue.slice(0, 5).map((job: any, index: number) => (
              <div key={index} style={{
                padding: '0.5rem',
                marginBottom: '0.5rem',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white'
              }}>
                <div style={{ fontWeight: 'bold', color: '#333' }}>{job.name || job.id}</div>
                <div style={{ color: '#666', fontSize: '0.8rem' }}>Type: {job.type}</div>
                <div style={{ color: '#666', fontSize: '0.8rem' }}>Position: #{index + 1}</div>
              </div>
            ))
          )}
        </div>

        {/* Currently Running Jobs */}
        <div style={{ padding: '1rem', border: '1px solid #007bff', borderRadius: '8px', backgroundColor: '#e7f3ff' }}>
          <h3 style={{ marginTop: 0, color: '#333', textAlign: 'center' }}>⚡ Running Jobs</h3>
          <div style={{ fontSize: '0.9rem', color: '#666', textAlign: 'center', marginBottom: '1rem' }}>
            {Object.values(jobStatus).filter((status: any) => status.status === 'running').length} active {Object.values(jobStatus).filter((status: any) => status.status === 'running').length > 5 && '(showing first 5)'}
          </div>
          {Object.keys(jobStatus).length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontStyle: 'italic' }}>No jobs running</div>
          ) : (
            Object.entries(jobStatus)
              .filter(([_, status]: [string, any]) => status.status === 'running')
              .slice(0, 5)
              .map(([jobId, status]: [string, any]) => (
                <div key={jobId} style={{
                  padding: '0.5rem',
                  marginBottom: '0.5rem',
                  border: '1px solid #007bff',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  position: 'relative'
                }}>
                  <div style={{ fontWeight: 'bold', color: '#333' }}>Job: {jobId}</div>
                  <div style={{ color: '#007bff', fontSize: '0.9rem' }}>🔄 {status.message}</div>
                  {status.start_time && (
                    <div style={{ color: '#666', fontSize: '0.8rem' }}>
                      Started: {new Date(status.start_time * 1000).toLocaleTimeString()}
                    </div>
                  )}
                  <button
                    onClick={() => killJob(jobId)}
                    style={{
                      position: 'absolute',
                      top: '0.5rem',
                      right: '0.5rem',
                      padding: '0.2rem 0.5rem',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '3px',
                      cursor: 'pointer',
                      fontSize: '0.7rem'
                    }}
                  >
                    Kill
                  </button>
                </div>
              ))
          )}
        </div>

        {/* Completed Jobs */}
        <div style={{ padding: '1rem', border: '1px solid #28a745', borderRadius: '8px', backgroundColor: '#d4edda' }}>
          <h3 style={{ marginTop: 0, color: '#333', textAlign: 'center' }}>✅ Recent Completions</h3>
          <div style={{ fontSize: '0.9rem', color: '#666', textAlign: 'center', marginBottom: '1rem' }}>
            {completedJobs.length} completed {completedJobs.length > 5 && '(showing latest 5)'}
          </div>
          {completedJobs.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontStyle: 'italic' }}>No completed jobs</div>
          ) : (
            completedJobs
              .slice(-5) // Show last 5 completed jobs
              .reverse() // Most recent first
              .map((status: any, index: number) => (
              <div key={`${status.job_id}-${index}`} style={{
                padding: '0.5rem',
                marginBottom: '0.5rem',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white'
              }}>
                <div style={{ fontWeight: 'bold', color: '#333' }}>Job: {status.job_id}</div>
                <div style={{
                  color: status.status === 'completed' ? '#28a745' : status.status === 'failed' ? '#dc3545' : '#6c757d',
                  fontSize: '0.9rem'
                }}>
                  {status.status === 'completed' ? '✅' : status.status === 'failed' ? '❌' : '🛑'} {status.status}
                </div>
                {status.end_time && (
                  <div style={{ color: '#666', fontSize: '0.8rem' }}>
                    Finished: {new Date(status.end_time * 1000).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Enhanced GPU Telemetry Grid */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ color: '#333', marginBottom: '1rem', textAlign: 'center' }}>🖥️ GPU Cluster Status</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {Object.keys(state.cluster_state).length === 0 ? (
            <div style={{ border: '1px solid #ccc', padding: '2rem', borderRadius: '8px', background: '#f8f9fa', textAlign: 'center', color: 'black', gridColumn: '1 / -1' }}>
              <p>🔄 No GPU data available. Waiting for telemetry...</p>
              <p style={{ color: '#666', fontSize: '0.9rem' }}>
                Make sure the Rust agent is running and publishing data.
              </p>
            </div>
          ) : (
            Object.entries(state.cluster_state).map(([gpuId, gpuState]) => {
              const gpu = gpuState as any;
              const utilization = gpu.utilization_gpu || 0;
              const temp = gpu.gpu_temp || gpu.temperature_c || 0;
              const memUsed = gpu.gpu_mem_used || gpu.memory_used_mb || 0;
              const memTotal = gpu.memory_total_mb || 24564;
              const power = gpu.power_draw_w || 0;
              const clock = gpu.clock_gpu_mhz || 0;
              const memClock = gpu.clock_mem_mhz || 0;

              // Color coding for different metrics
              const getUtilColor = (util: number) => util > 80 ? '#dc3545' : util > 50 ? '#ffc107' : '#28a745';
              const getTempColor = (temp: number) => temp > 80 ? '#dc3545' : temp > 70 ? '#ffc107' : '#28a745';
              const getMemColor = (used: number, total: number) => {
                const percent = (used / total) * 100;
                return percent > 80 ? '#dc3545' : percent > 60 ? '#ffc107' : '#28a745';
              };

              return (
                <div key={gpuId} style={{
                  border: state.anomalies[gpuId] ? '2px solid #dc3545' : '1px solid #dee2e6',
                  padding: '1rem',
                  borderRadius: '8px',
                  background: state.anomalies[gpuId] ? '#fff5f5' : '#ffffff',
                  color: 'black',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                  position: 'relative'
                }}>
                  {/* GPU Header */}
                  <div style={{ borderBottom: '1px solid #dee2e6', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
                    <h4 style={{ margin: 0, fontSize: '1.1rem', color: '#333' }}>
                      {gpu.gpu_name || gpuId.toUpperCase()}
                    </h4>
                    <div style={{ fontSize: '0.8rem', color: '#666' }}>
                      ID: {gpuId} • Performance: {gpu.performance_state || 'P2'}
                    </div>
                  </div>

                  {/* Utilization Bar */}
                  <div style={{ marginBottom: '0.8rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: '500' }}>GPU Utilization</span>
                      <span style={{ fontSize: '0.9rem', color: getUtilColor(utilization) }}>{utilization}%</span>
                    </div>
                    <div style={{
                      height: '8px',
                      backgroundColor: '#e9ecef',
                      borderRadius: '4px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${utilization}%`,
                        backgroundColor: getUtilColor(utilization),
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                  </div>

                  {/* Memory Usage */}
                  <div style={{ marginBottom: '0.8rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: '500' }}>Memory</span>
                      <span style={{ fontSize: '0.9rem', color: getMemColor(memUsed, memTotal) }}>
                        {memUsed.toLocaleString()} / {memTotal.toLocaleString()} MB
                      </span>
                    </div>
                    <div style={{
                      height: '8px',
                      backgroundColor: '#e9ecef',
                      borderRadius: '4px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${(memUsed / memTotal) * 100}%`,
                        backgroundColor: getMemColor(memUsed, memTotal),
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                  </div>

                  {/* Key Metrics Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', fontSize: '0.9rem' }}>
                    <div>
                      <div style={{ color: '#666', fontSize: '0.8rem' }}>Temperature</div>
                      <div style={{ color: getTempColor(temp), fontWeight: '500' }}>{temp}°C</div>
                    </div>
                    <div>
                      <div style={{ color: '#666', fontSize: '0.8rem' }}>Power Draw</div>
                      <div style={{ fontWeight: '500' }}>{power}W</div>
                    </div>
                    <div>
                      <div style={{ color: '#666', fontSize: '0.8rem' }}>GPU Clock</div>
                      <div style={{ fontWeight: '500' }}>{clock} MHz</div>
                    </div>
                    <div>
                      <div style={{ color: '#666', fontSize: '0.8rem' }}>Memory Clock</div>
                      <div style={{ fontWeight: '500' }}>{memClock} MHz</div>
                    </div>
                  </div>

                  {/* Throttling/Anomaly Indicators */}
                  {gpu.throttling_reasons && gpu.throttling_reasons !== 'None' && (
                    <div style={{
                      marginTop: '0.8rem',
                      padding: '0.4rem',
                      backgroundColor: '#fff3cd',
                      border: '1px solid #ffeaa7',
                      borderRadius: '4px',
                      fontSize: '0.8rem'
                    }}>
                      ⚠️ Throttled: {gpu.throttling_reasons}
                    </div>
                  )}

                  {state.anomalies[gpuId] && (
                    <div style={{
                      position: 'absolute',
                      top: '0.5rem',
                      right: '0.5rem',
                      padding: '0.2rem 0.4rem',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      borderRadius: '3px',
                      fontSize: '0.7rem',
                      fontWeight: 'bold'
                    }}>
                      🚨 ANOMALY
                    </div>
                  )}
                </div>
              );
            })
          )}
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
