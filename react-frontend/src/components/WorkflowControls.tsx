
import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { workflowApi, healthApi, transcriptionSettingsApi } from '@/lib/api';
import { Play, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import { FileUploadButton } from './FileUploadButton';

export const WorkflowControls: React.FC = () => {
  const queryClient = useQueryClient();
  const [awsHostValue, setAwsHostValue] = useState<string>('');

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

  // AWS Host Setting Query
  const { data: awsHostData, isLoading: awsHostLoading } = useQuery({
    queryKey: ['transcription-settings', 'aws_host'],
    queryFn: () => transcriptionSettingsApi.get('aws_host'),
    onSuccess: (data) => {
      if (data.data?.value) {
        setAwsHostValue(data.data.value);
      }
    },
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

  // Save AWS Host Mutation
  const saveAwsHostMutation = useMutation({
    mutationFn: (value: string) => transcriptionSettingsApi.update('aws_host', value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcription-settings', 'aws_host'] });
    },
    onError: (error) => {
      console.error('Fehler beim Speichern des AWS Host:', error);
    },
  });

  const handleSaveAwsHost = () => {
    if (awsHostValue.trim()) {
      saveAwsHostMutation.mutate(awsHostValue.trim());
    }
  };

  const handleAwsHostKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSaveAwsHost();
      e.currentTarget.blur();
    }
  };

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

      {/* AWS Host Input */}
      <div className="mt-4 mb-4">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          AWS Host/IP
        </label>
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={awsHostValue}
            onChange={(e) => setAwsHostValue(e.target.value)}
            onBlur={handleSaveAwsHost}
            onKeyDown={handleAwsHostKeyDown}
            placeholder="z.B. 192.168.1.100 oder ec2-xxx.amazonaws.com"
            disabled={awsHostLoading || saveAwsHostMutation.isPending}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed"
          />
          {saveAwsHostMutation.isPending && (
            <div className="animate-spin h-5 w-5 border-2 border-blue-500 rounded-full border-t-transparent"></div>
          )}
        </div>
        {saveAwsHostMutation.isError && (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">
            Fehler beim Speichern
          </p>
        )}
        {saveAwsHostMutation.isSuccess && !saveAwsHostMutation.isPending && (
          <p className="mt-1 text-xs text-green-600 dark:text-green-400">
            Gespeichert
          </p>
        )}
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

          <FileUploadButton
            onSuccess={() => {
              // Erfolgsmeldung anzeigen
              alert('CSV erfolgreich importiert!');
              // Optional: Workflow-Status neu laden
              // queryClient.invalidateQueries({ queryKey: ['workflow-status'] });
            }}
            onError={(error) => {
              // Fehlermeldung anzeigen
              alert(`Fehler beim CSV-Import: ${error}`);
            }}
          />

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