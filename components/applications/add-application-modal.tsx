'use client'

import React from "react"

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useState } from 'react'
import { Plus } from 'lucide-react'

interface AddApplicationModalProps {
  onAdd: (data: any) => void
}

export function AddApplicationModal({ onAdd }: AddApplicationModalProps) {
  const [open, setOpen] = useState(false)
  const [formData, setFormData] = useState({
    company_name: '',
    role: '',
    status: 'Applied',
    applied_date: new Date().toISOString().split('T')[0],
    interview_date: '',
    deadline_date: '',
    notes: '',
    job_description: '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Clean data for backend (Pydantic crashes if we send '' for datetime)
    const cleanedData = {
      ...formData,
      interview_date: formData.interview_date ? formData.interview_date : null,
      deadline_date: formData.deadline_date ? formData.deadline_date : null,
      job_description: formData.job_description ? formData.job_description : null
    }

    onAdd(cleanedData)

    setFormData({
      company_name: '',
      role: '',
      status: 'Applied',
      applied_date: new Date().toISOString().split('T')[0],
      interview_date: '',
      deadline_date: '',
      notes: '',
      job_description: '',
    })
    setOpen(false)
  }

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        className="bg-gradient-to-r from-primary to-secondary hover:opacity-90 text-white"
      >
        <Plus className="w-4 h-4 mr-2" />
        Add Application
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="glass border-white/10">
          <DialogHeader>
            <DialogTitle>Add New Application</DialogTitle>
            <DialogDescription>
              Track a new internship application
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Company Name</label>
              <Input
                type="text"
                placeholder="Google, Microsoft, etc."
                className="glass border-white/10 rounded-lg"
                value={formData.company_name}
                onChange={(e) =>
                  setFormData({ ...formData, company_name: e.target.value })
                }
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Role</label>
              <Input
                type="text"
                placeholder="Software Engineer Intern"
                className="glass border-white/10 rounded-lg"
                value={formData.role}
                onChange={(e) =>
                  setFormData({ ...formData, role: e.target.value })
                }
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value })
                }
              >
                <SelectTrigger className="glass border-white/10 rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border-white/10">
                  <SelectItem value="Applied">Applied</SelectItem>
                  <SelectItem value="Interview">Interview</SelectItem>
                  <SelectItem value="Selected">Selected</SelectItem>
                  <SelectItem value="Rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Applied Date</label>
              <Input
                type="date"
                className="glass border-white/10 rounded-lg"
                value={formData.applied_date}
                onChange={(e) =>
                  setFormData({ ...formData, applied_date: e.target.value })
                }
                required
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Deadline (Optional)</label>
                <Input
                  type="date"
                  className="glass border-white/10 rounded-lg"
                  value={formData.deadline_date}
                  onChange={(e) =>
                    setFormData({ ...formData, deadline_date: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Interview Date (Optional)</label>
                <Input
                  type="date"
                  className="glass border-white/10 rounded-lg"
                  value={formData.interview_date}
                onChange={(e) =>
                  setFormData({ ...formData, interview_date: e.target.value })
                }
              />
            </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Job Description (Optional)</label>
              <textarea
                placeholder="Paste the target JD here to power the AI compatibility score..."
                className="w-full min-h-[120px] text-sm p-3 glass border border-white/10 rounded-lg resize-y bg-black/20 focus:bg-white/5 transition-colors"
                value={formData.job_description}
                onChange={(e) =>
                  setFormData({ ...formData, job_description: e.target.value })
                }
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Notes (Optional)</label>
              <textarea
                placeholder="Feedback, interviewer name, etc..."
                className="w-full min-h-[80px] text-sm p-3 glass border border-white/10 rounded-lg resize-y"
                value={formData.notes}
                onChange={(e) =>
                  setFormData({ ...formData, notes: e.target.value })
                }
              />
            </div>

            <div className="flex gap-3 justify-end pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                className="border-white/10"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="bg-primary hover:bg-primary/90 text-white"
              >
                Add Application
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
