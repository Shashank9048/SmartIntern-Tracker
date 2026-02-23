import { CheckCircle, AlertCircle } from 'lucide-react'

interface AnalysisResultsProps {
  matchScore: number
  missingKeywords: string[]
  improvements: string[]
}

export function AnalysisResults({
  matchScore,
  missingKeywords,
  improvements,
}: AnalysisResultsProps) {
  return (
    <div className="space-y-6">
      {/* Match Score */}
      <div className="glass rounded-xl p-8 glow text-center">
        <p className="text-sm text-muted-foreground mb-4">Match Score</p>
        <div className="relative w-40 h-40 mx-auto mb-6">
          <svg className="w-full h-full transform -rotate-90">
            <circle
              cx="80"
              cy="80"
              r="70"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="8"
              fill="none"
            />
            <circle
              cx="80"
              cy="80"
              r="70"
              stroke="url(#gradient)"
              strokeWidth="8"
              fill="none"
              strokeDasharray={`${(matchScore / 100) * 440} 440`}
              style={{ transition: 'stroke-dasharray 0.5s' }}
            />
            <defs>
              <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#00d9ff" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <div>
              <p className="text-4xl font-bold">{matchScore}%</p>
              <p className="text-sm text-muted-foreground">Match</p>
            </div>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Your resume aligns well with this job description
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Missing Keywords */}
        <div className="glass rounded-xl p-6 glow">
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="w-5 h-5 text-yellow-500" />
            <h3 className="text-lg font-semibold">Missing Keywords</h3>
          </div>

          <div className="flex flex-wrap gap-2">
            {missingKeywords.map((keyword) => (
              <div
                key={keyword}
                className="bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full text-sm"
              >
                {keyword}
              </div>
            ))}
          </div>
        </div>

        {/* Improvements */}
        <div className="glass rounded-xl p-6 glow">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <h3 className="text-lg font-semibold">Improvement Suggestions</h3>
          </div>

          <ul className="space-y-3">
            {improvements.map((improvement, index) => (
              <li key={index} className="flex gap-3 text-sm">
                <span className="text-green-500 font-bold flex-shrink-0">
                  ✓
                </span>
                <span className="text-muted-foreground">{improvement}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
