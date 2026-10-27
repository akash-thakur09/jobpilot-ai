import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick,
  hoverable = false,
}) => {
  return (
    <div
      onClick={onClick}
      className={`bg-slate-900/70 border border-slate-800/80 rounded-xl p-5 shadow-sm backdrop-blur-sm ${
        hoverable
          ? 'hover:border-slate-700 hover:bg-slate-900 transition-all cursor-pointer'
          : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};
