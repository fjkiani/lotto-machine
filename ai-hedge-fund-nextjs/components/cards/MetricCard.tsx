import { ReactNode } from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: string | number;
  icon?: ReactNode;
  isPositive?: boolean;
  isNegative?: boolean;
  formatter?: (value: string | number) => string;
}

export default function MetricCard({
  title,
  value,
  change,
  icon,
  isPositive,
  isNegative,
  formatter = (v) => String(v),
}: MetricCardProps) {
  const formattedValue = formatter(value);
  
  let changeColorClass = '';
  
  if (isPositive) {
    changeColorClass = 'text-success-500';
  } else if (isNegative) {
    changeColorClass = 'text-danger-500';
  }
  
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300">{title}</h3>
        {icon && <div className="text-gray-500">{icon}</div>}
      </div>
      
      <div className="text-3xl font-bold">{formattedValue}</div>
      
      {change !== undefined && (
        <div className={`mt-2 text-sm ${changeColorClass}`}>
          {isPositive && '+'}{change}
          {typeof change === 'number' && '%'}
        </div>
      )}
    </div>
  );
} 