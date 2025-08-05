import React from 'react';
import { Badge } from './ui/badge';
import { getStatusColor, getStatusText } from '@/lib/data-formatters';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  const statusColor = getStatusColor(status);
  const statusText = getStatusText(status);

  return (
    <Badge className={`${statusColor} ${className || ''}`}>
      {statusText}
    </Badge>
  );
}; 