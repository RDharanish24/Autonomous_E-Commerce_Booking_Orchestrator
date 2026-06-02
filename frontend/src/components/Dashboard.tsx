import React from 'react';
import { useStore } from '../store/useStore';

const Dashboard: React.FC = () => {
  const { isDarkMode, toggleDarkMode, bookingConstraints, setBookingConstraints } = useStore();

  return (
    <div className={`min-h-screen ${isDarkMode ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'} p-8 transition-colors duration-300`}>
      <header className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
            Autonomous Orchestrator
          </h1>
          <p className="text-sm opacity-70 mt-1">AI-Powered E-Commerce & Booking</p>
        </div>
        <button
          onClick={toggleDarkMode}
          className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 hover:bg-gray-700 transition-all text-sm font-medium"
        >
          Toggle {isDarkMode ? 'Light' : 'Dark'} Mode
        </button>
      </header>

      <main className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Status Card */}
        <section className={`p-6 rounded-2xl ${isDarkMode ? 'bg-gray-800/50 border border-gray-700' : 'bg-white border border-gray-200 shadow-sm'}`}>
          <h2 className="text-lg font-semibold mb-4 flex items-center">
            <span className="w-2 h-2 rounded-full bg-green-500 mr-2 animate-pulse"></span>
            System Status
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="opacity-70">Backend API</span>
              <span className="text-green-400 font-medium">Operational</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-70">Database</span>
              <span className="text-green-400 font-medium">Connected</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-70">AI Engine</span>
              <span className="text-yellow-400 font-medium">Standby</span>
            </div>
          </div>
        </section>

        {/* Booking Constraints Card */}
        <section className={`p-6 rounded-2xl md:col-span-2 ${isDarkMode ? 'bg-gray-800/50 border border-gray-700' : 'bg-white border border-gray-200 shadow-sm'}`}>
          <h2 className="text-lg font-semibold mb-4">Booking Constraints</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
            <button className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
              Initialize Agents
            </button>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Dashboard;
