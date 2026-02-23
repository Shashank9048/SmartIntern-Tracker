import { type LucideIcon } from 'lucide-react'

interface SummaryCardProps {
  title: string
  value: number
  icon: LucideIcon
  color: 'primary' | 'secondary' | 'accent'
}

export function SummaryCard({
  title,
  value,
  icon: Icon,
  color,
}: SummaryCardProps) {
  const colorClasses = {
    primary: 'from-primary to-primary/50 text-primary',
    secondary: 'from-secondary to-secondary/50 text-secondary',
    accent: 'from-accent to-accent/50 text-accent',
  }

  return (
    <div className="glass rounded-xl p-6 glow hover:bg-white/10 transition-all duration-300">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground mb-2">
            {title}
          </p>
          <p className="text-3xl font-bold">{value}</p>
        </div>
        <div
          className={`bg-gradient-to-br ${colorClasses[color]} w-12 h-12 rounded-lg flex items-center justify-center`}
        >
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}
