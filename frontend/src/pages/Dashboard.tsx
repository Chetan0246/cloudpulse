/**
 * Main dashboard page.
 * 
 * Implemented in Phase 7. Currently shows a placeholder.
 * Polls /resources and /incidents every VITE_POLL_INTERVAL_MS milliseconds.
 */
function Dashboard() {
  return (
    <div className="text-center py-20 text-gray-500">
      <p className="text-lg">Dashboard — Phase 7</p>
      <p className="text-sm mt-2">
        Resource cards, incident table, and metrics charts will be built here.
      </p>
    </div>
  );
}

export default Dashboard;
