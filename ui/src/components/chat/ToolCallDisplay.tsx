import { LoaderIcon, CheckIcon, AlertIcon, TerminalIcon } from '../icons'

interface ToolCallDisplayProps {
  name: string;
  status: 'running' | 'completed' | 'error';
  output?: string;
  is_error?: boolean;
}

export function ToolCallDisplay({ name, status, output, is_error }: ToolCallDisplayProps) {
  const statusConfig = {
    running: {
      icon: <LoaderIcon size={14} className="animate-spin" />,
      color: 'text-amber-400',
      bgColor: 'bg-amber-400/10',
      borderColor: 'border-amber-400/20',
      label: 'Running',
    },
    completed: {
      icon: <CheckIcon size={14} />,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-400/10',
      borderColor: 'border-emerald-400/20',
      label: 'Done',
    },
    error: {
      icon: <AlertIcon size={14} />,
      color: 'text-red-400',
      bgColor: 'bg-red-400/10',
      borderColor: 'border-red-400/20',
      label: 'Error',
    },
  }[status]

  return (
    <div className="flex gap-3 px-4 py-3 animate-in slide-in-from-bottom-1 fade-in duration-200">
      <div className="w-8 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className={`rounded-lg border ${statusConfig.borderColor} ${statusConfig.bgColor} overflow-hidden`}>
          {/* Header */}
          <div className="flex items-center gap-3 px-3 py-2 border-b border-border/50 bg-background/50">
            <TerminalIcon size={14} className="text-muted-foreground" />
            <span className="font-mono text-sm font-medium text-foreground">{name}</span>
            <div className={`ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.color} bg-background/80`}>
              {statusConfig.icon}
              <span>{statusConfig.label}</span>
            </div>
          </div>
          
          {/* Output */}
          {output && !is_error && (
            <div className="max-h-40 overflow-y-auto">
              <pre className="px-3 py-2 text-xs text-muted-foreground font-mono whitespace-pre-wrap">
                {output.length > 500 ? output.slice(0, 500) + '...' : output}
              </pre>
            </div>
          )}
          {output && is_error && (
            <div className="px-3 py-2 bg-red-400/5">
              <pre className="text-xs text-red-400 font-mono whitespace-pre-wrap">
                {output}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
