import React, { useRef, useEffect } from 'react';
import { useStore, type LogEvent } from '../store/useStore';
import { useOrchestratorSocket } from '../hooks/useOrchestratorSocket';

const Dashboard: React.FC = () => {
  const {
    isDarkMode,
    toggleDarkMode,
    bookingConstraints,
    setBookingConstraints,
    isConnected,
    clientId,
    logs,
    clearLogs,
    finalDecision
  } = useStore();

  // Initialize the WebSocket connection
  useOrchestratorSocket();

  // Auto-scroll the live feed to bottom
  const logsEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleInitialize = async () => {
    clearLogs();
    try {
      const response = await fetch('http://localhost:8000/api/v1/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: `Book a ${bookingConstraints.serviceType || 'service'}`,
          constraints: bookingConstraints,
          client_id: clientId // Send client_id so the backend knows where to push updates
        })
      });
      if (!response.ok) throw new Error('Orchestration failed to start');
    } catch (error) {
      console.error(error);
      useStore.getState().addLog({
        timestamp: new Date().toISOString(),
        status: 'Error starting orchestration pipeline',
      });
    }
  };

  return (
    <div className={`min-h-screen ${isDarkMode ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'} p-8 transition-colors duration-300`}>
      <header className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
            Autonomous Orchestrator
          </h1>
          <p className="text-sm opacity-70 mt-1">Phase 4: Real-Time Websockets</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-gray-800 px-3 py-1.5 rounded-lg border border-gray-700">
            <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></span>
            <span className="text-xs font-mono">{isConnected ? 'WS Connected' : 'WS Disconnected'}</span>
          </div>
          <button
            onClick={toggleDarkMode}
            className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 hover:bg-gray-700 transition-all text-sm font-medium"
          >
            Toggle {isDarkMode ? 'Light' : 'Dark'} Mode
          </button>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Constraints & Final Decision */}
        <div className="lg:col-span-1 space-y-6">
          <section className={`p-6 rounded-2xl ${isDarkMode ? 'bg-gray-800/50 border border-gray-700' : 'bg-white border border-gray-200 shadow-sm'}`}>
            <h2 className="text-lg font-semibold mb-4">Booking Constraints</h2>
            <div className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs opacity-70 uppercase tracking-wider">Service Type</label>
                <input
                  type="text"
                  className={`w-full p-2.5 rounded-lg text-sm transition-colors ${isDarkMode ? 'bg-gray-900 border border-gray-700 focus:border-blue-500 outline-none' : 'bg-gray-50 border border-gray-200 focus:border-blue-500 outline-none'}`}
                  placeholder="e.g. Flight, Hotel"
                  value={bookingConstraints.serviceType || ''}
                  onChange={(e) => setBookingConstraints({ serviceType: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs opacity-70 uppercase tracking-wider">Max Price ($)</label>
                <input
                  type="number"
                  className={`w-full p-2.5 rounded-lg text-sm transition-colors ${isDarkMode ? 'bg-gray-900 border border-gray-700 focus:border-blue-500 outline-none' : 'bg-gray-50 border border-gray-200 focus:border-blue-500 outline-none'}`}
                  placeholder="0.00"
                  value={bookingConstraints.maxPrice || ''}
                  onChange={(e) => setBookingConstraints({ maxPrice: parseFloat(e.target.value) })}
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={handleInitialize}
                disabled={!isConnected}
                className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${isConnected ? 'bg-blue-600 hover:bg-blue-500 text-white' : 'bg-gray-600 text-gray-300 cursor-not-allowed'}`}
              >
                Initialize Agents
              </button>
            </div>
          </section>

          {/* Decision Card */}
          {finalDecision && (
            <section className={`p-6 rounded-2xl border ${finalDecision.error ? 'bg-red-900/20 border-red-700' : (isDarkMode ? 'bg-green-900/20 border-green-700' : 'bg-green-50 border-green-200')} shadow-sm transition-all duration-500`}>
              <h2 className="text-lg font-semibold mb-4 flex items-center">
                {finalDecision.error ? 'Human Review Required' : 'Optimal Decision Reached'}
              </h2>
              {finalDecision.error ? (
                <div className="text-sm space-y-2">
                  <p className="text-red-400 font-mono text-xs">{finalDecision.error}</p>
                  <p className="opacity-80">Failed at phase: {finalDecision.phase}</p>
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between items-center border-b border-gray-700/50 pb-2">
                    <span className="opacity-70">Selected Flight</span>
                    <span className="font-mono bg-gray-800 px-2 py-1 rounded text-blue-400">{finalDecision.selected_flight_id}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-gray-700/50 pb-2">
                    <span className="opacity-70">Vendor</span>
                    <span className="font-medium text-purple-400">{finalDecision.vendor_name}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-gray-700/50 pb-2">
                    <span className="opacity-70">Total Cost</span>
                    <span className="font-bold text-green-400">${finalDecision.total_cost}</span>
                  </div>
                  <div className="pt-2">
                    <span className="opacity-70 block mb-1">AI Reasoning</span>
                    <p className="italic text-gray-300 leading-relaxed bg-gray-900/50 p-3 rounded-lg border border-gray-700/50">"{finalDecision.reasoning}"</p>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>

        {/* Right Column: Live Activity Feed */}
        <section className={`lg:col-span-2 p-6 rounded-2xl flex flex-col h-[600px] ${isDarkMode ? 'bg-gray-900 border border-gray-700' : 'bg-black border border-gray-800'} font-mono text-sm shadow-xl`}>
          <div className="flex items-center space-x-2 mb-4 border-b border-gray-700 pb-4">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="ml-4 text-gray-400 text-xs tracking-widest uppercase">Live Activity Feed</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar pr-2">
            {logs.length === 0 ? (
              <p className="text-gray-500 italic text-center mt-10">Awaiting orchestration commands...</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="animate-fade-in-up">
                  <div className="flex items-start space-x-3">
                    <span className="text-gray-500 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                    <div>
                      <span className="text-blue-400">{log.status}</span>
                      {log.payload && (
                        <pre className="mt-1 text-xs text-gray-400 bg-gray-800/50 p-2 rounded border border-gray-700/50 overflow-x-auto">
                          {JSON.stringify(log.payload, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </section>

      </main>
    </div>
  );
};

export default Dashboard;
