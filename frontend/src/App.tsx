import Dashboard from './pages/Dashboard';

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold tracking-tight">
          ☁️ CloudPulse
          <span className="ml-2 text-sm font-normal text-gray-400">
            Autonomous Cloud Reliability Simulator
          </span>
        </h1>
      </header>
      <main className="px-6 py-6">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;
