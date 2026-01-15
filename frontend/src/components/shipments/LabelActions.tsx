import { Printer, Download, Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { Button } from '../ui'
import { cn } from '../../lib/utils'

interface LabelActionsProps {
  labelUrl: string
  trackingNumber: string
  className?: string
}

export function LabelActions({ labelUrl, trackingNumber, className }: LabelActionsProps) {
  const [copied, setCopied] = useState(false)

  const handlePrint = () => {
    const printWindow = window.open(labelUrl, '_blank')
    if (printWindow) {
      printWindow.onload = () => {
        printWindow.print()
      }
    }
  }

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = labelUrl
    link.download = `label-${trackingNumber}.pdf`
    link.click()
  }

  const handleCopyTracking = async () => {
    await navigator.clipboard.writeText(trackingNumber)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      <Button variant="default" size="sm" onClick={handlePrint}>
        <Printer className="h-4 w-4 mr-2" />
        Print
      </Button>

      <Button variant="default" size="sm" onClick={handleDownload}>
        <Download className="h-4 w-4 mr-2" />
        Download
      </Button>

      <Button variant="default" size="sm" onClick={handleCopyTracking}>
        {copied ? (
          <>
            <Check className="h-4 w-4 mr-2 text-accent-green" />
            Copied!
          </>
        ) : (
          <>
            <Copy className="h-4 w-4 mr-2" />
            Copy Tracking
          </>
        )}
      </Button>
    </div>
  )
}
