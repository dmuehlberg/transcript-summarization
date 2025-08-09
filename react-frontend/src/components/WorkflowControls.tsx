
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { workflowApi, healthApi } from '@/lib/api';
import { Play, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

export const WorkflowControls: React.FC = () => {
  // Health Status Query
  const { data: healthData, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.check(),
    refetchInterval: 30000, // Alle 30 Sekunden
  });

  // Workflow Status Query
  const { data: workflowData, isLoading: workflowLoading } = useQuery({
    queryKey: ['workflow-status'],
    queryFn: () => workflowApi.getStatus(),
    refetchInterval: 5000, // Alle 5 Sekunden
  });

  // Start Workflow Mutation
  const startWorkflowMutation = useMutation({
    mutationFn: () => workflowApi.start(),
    onSuccess: () => {
      // Refetch workflow status after starting
      // QueryClient wird automatisch invalidiert
    },
    onError: (error) => {
      console.error('Fehler beim Starten des Workflows:', error);
    },
  });

  const handleStartWorkflow = () => {
    startWorkflowMutation.mutate();
  };

  const getHealthIcon = (isHealthy: boolean) => {
    return isHealthy ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    );
  };

  const getWorkflowStatusColor = (status?: string) => {
    switch (status) {
      case 'running':
        return 'bg-blue-500 text-white';
      case 'active':
        return 'bg-green-500 text-white';
      case 'stopped':
        return 'bg-gray-500 text-white';
      case 'error':
        return 'bg-red-500 text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Workflow-Steuerung
        </h2>
        <div className="flex items-center space-x-4">
          {/* Health Status */}
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Datenbank:</span>
            {healthLoading ? (
              <div className="animate-spin h-4 w-4 border-2 border-blue-500 rounded-full border-t-transparent"></div>
            ) : (
              getHealthIcon(healthData?.data?.database || false)
            )}
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">n8n:</span>
            {healthLoading ? (
              <div className="animate-spin h-4 w-4 border-2 border-blue-500 rounded-full border-t-transparent"></div>
            ) : (
              getHealthIcon(healthData?.data?.n8n || false)
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button
            onClick={handleStartWorkflow}
            disabled={startWorkflowMutation.isPending || !healthData?.data?.n8n}
            className="flex items-center space-x-2"
          >
            <Play className="h-4 w-4" />
            <span>Transkription starten</span>
          </Button>

          {startWorkflowMutation.isPending && (
            <div className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-blue-500 rounded-full border-t-transparent"></div>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Workflow wird gestartet...
              </span>
            </div>
          )}
        </div>

        {/* Workflow Status */}
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">Status:</span>
          {workflowLoading ? (
            <div className="animate-spin h-4 w-4 border-2 border-blue-500 rounded-full border-t-transparent"></div>
          ) : (
            <Badge className={getWorkflowStatusColor(workflowData?.data.status)}>
              {workflowData?.data.status || 'Unbekannt'}
            </Badge>
          )}
        </div>
      </div>

      {/* Error Display */}
      {startWorkflowMutation.isError && (
        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
          <div className="flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm text-red-700 dark:text-red-400">
              Fehler beim Starten des Workflows
            </span>
          </div>
        </div>
      )}
    </div>
  );
}; 