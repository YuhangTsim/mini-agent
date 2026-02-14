interface ToolCallDisplayProps {
  name: string;
  status: 'running' | 'completed' | 'error';
  output?: string;
  is_error?: boolean;
}

export function ToolCallDisplay({ name, status, output, is_error }: ToolCallDisplayProps) {
  const statusIcon = {
    running: '...',
    completed: 'OK',
    error: '!!',
  }[status]

  const statusColor = {
    running: 'text-yellow-600 dark:text-yellow-400',
    completed: 'text-green-600 dark:text-green-400',
    error: 'text-red-600 dark:text-red-400',
  }[status]

  return (
    <div className="flex gap-3 px-4 py-2">
      <div className="w-8 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-mono text-muted-foreground">Tool:</span>
          <span className="font-mono font-medium">{name}</span>
          <span className={`font-mono text-xs ${statusColor}`}>
            [{statusIcon}]
          </span>
          {status === 'running' && (
            <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          )}
        </div>
        {output && !is_error && (
          <pre className="mt-1 text-xs text-muted-foreground font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
            {output.length > 500 ? output.slice(0, 500) + '...' : output}
          </pre>
        )}
        {output && is_error && (
          <pre className="mt-1 text-xs text-red-600 dark:text-red-400 font-mono whitespace-pre-wrap">
            {output}
          </pre>
        )}
      </div>
    </div>
  )
}
