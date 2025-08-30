import { useState } from 'react';
import { WorkflowControls } from './components/WorkflowControls';
import { TranscriptionTable } from './components/TranscriptionTable';
import { CalendarTable } from './components/CalendarTable';

type Screen = 'dashboard' | 'calendar';

interface CalendarScreenState {
  transcriptionId: number;
  startDate: string;
}

function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('dashboard');
  const [calendarState, setCalendarState] = useState<CalendarScreenState | null>(null);

  const handleSelectMeeting = (transcriptionId: number, startDate: string) => {
    setCalendarState({ transcriptionId, startDate });
    setCurrentScreen('calendar');
  };

  const handleCalendarBack = () => {
    setCurrentScreen('dashboard');
    setCalendarState(null);
  };

  const handleCalendarSuccess = () => {
    setCurrentScreen('dashboard');
    setCalendarState(null);
  };

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
          {currentScreen === 'dashboard' && (
            <>
              <WorkflowControls />
              <TranscriptionTable onSelectMeeting={handleSelectMeeting} />
            </>
          )}

          {currentScreen === 'calendar' && calendarState && (
            <CalendarTable
              transcriptionId={calendarState.transcriptionId}
              startDate={calendarState.startDate}
              onBack={handleCalendarBack}
              onSuccess={handleCalendarSuccess}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App; 