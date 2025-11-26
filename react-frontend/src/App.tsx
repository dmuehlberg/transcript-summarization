import { WorkflowControls } from './components/WorkflowControls';
import { TranscriptionTable } from './components/TranscriptionTable';

function App() {
  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      <div className="w-full max-w-none px-4 py-8">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Transkriptions-Steuerung
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Verwaltung und Steuerung von Audio-Transkriptionen
          </p>
        </header>

        <main>
          <WorkflowControls />
          <TranscriptionTable />
        </main>
      </div>
    </div>
  );
}

export default App; 