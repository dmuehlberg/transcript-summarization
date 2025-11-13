import React, { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { csvImportApi } from '../lib/api';

interface FileUploadButtonProps {
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export const FileUploadButton: React.FC<FileUploadButtonProps> = ({ 
  onSuccess, 
  onError 
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  
  const importMutation = useMutation({
    mutationFn: (file: File) => csvImportApi.importCalendarCsv(file, 'internal'),
    onSuccess: () => {
      setIsUploading(false);
      // File-Input zurücksetzen, damit beim nächsten Mal das onChange-Event wieder ausgelöst wird
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onSuccess?.();
    },
    onError: (error: Error) => {
      setIsUploading(false);
      // File-Input zurücksetzen, damit beim nächsten Mal das onChange-Event wieder ausgelöst wird
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onError?.(error.message);
    },
  });
  
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setIsUploading(true);
      importMutation.mutate(file);
    }
  };
  
  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };
  
  return (
    <div className="flex items-center space-x-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        onChange={handleFileSelect}
        className="hidden"
      />
      <button
        onClick={handleButtonClick}
        disabled={isUploading}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isUploading ? 'Importiere...' : 'Kalender CSV importieren'}
      </button>
    </div>
  );
};
