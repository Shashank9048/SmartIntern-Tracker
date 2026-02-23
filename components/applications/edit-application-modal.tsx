'use client'

import React, { useState, useEffect } from "react"
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
import { Application } from "@/types"

interface EditApplicationModalProps {
    application: Application | null
    open: boolean
    onOpenChange: (open: boolean) => void
    onUpdate: (id: string, data: any) => void
}

export function EditApplicationModal({ application, open, onOpenChange, onUpdate }: EditApplicationModalProps) {
    const [formData, setFormData] = useState({
        company_name: '',
        role: '',
        status: 'Applied',
        applied_date: '',
        interview_date: '',
        notes: '',
    })

    useEffect(() => {
        if (application) {
            setFormData({
                company_name: application.company_name || '',
                role: application.role || '',
                status: application.status || 'Applied',
                applied_date: application.applied_date ? new Date(application.applied_date).toISOString().split('T')[0] : '',
                interview_date: application.interview_date ? new Date(application.interview_date).toISOString().split('T')[0] : '',
                notes: application.notes || '',
            })
        }
    }, [application])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (application) {
            const cleanedData = {
                ...formData,
                interview_date: formData.interview_date ? formData.interview_date : null
            }
            onUpdate(application._id, cleanedData)
        }
        onOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="glass border-white/10">
                <DialogHeader>
                    <DialogTitle>Edit Application</DialogTitle>
                    <DialogDescription>
                        Update your internship application tracking details
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
                            onClick={() => onOpenChange(false)}
                            className="border-white/10"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            className="bg-primary hover:bg-primary/90 text-white"
                        >
                            Save Changes
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    )
}
