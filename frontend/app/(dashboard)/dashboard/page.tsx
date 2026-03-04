"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader2, CheckCircle2, XCircle, Clock, PlayCircle, Video, TrendingUp, Zap } from "lucide-react"

export default function DashboardPage() {
    const { data: jobs, isLoading } = useQuery({
        queryKey: ["jobs"],
        queryFn: async () => {
            const res = await api.get("/jobs")
            return res.data
        },
        refetchInterval: 5000
    })

    const { data: usage } = useQuery({
        queryKey: ["usage"],
        queryFn: async () => {
            try {
                const res = await api.get("/usage")
                return res.data
            } catch { return null }
        }
    })

    const totalJobs = jobs?.length || 0
    const completedJobs = jobs?.filter((j: any) => j.status === "completed").length || 0
    const runningJobs = jobs?.filter((j: any) => j.status === "running").length || 0
    const failedJobs = jobs?.filter((j: any) => j.status === "failed").length || 0

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "completed":
                return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"><CheckCircle2 className="h-3 w-3" /> Completed</span>
            case "failed":
                return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"><XCircle className="h-3 w-3" /> Failed</span>
            case "running":
                return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"><Loader2 className="h-3 w-3 animate-spin" /> Running</span>
            case "pending":
                return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"><Clock className="h-3 w-3" /> Pending</span>
            default:
                return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{status}</span>
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
                <Link href="/jobs/create">
                    <Button><Zap className="h-4 w-4 mr-2" /> New Automation</Button>
                </Link>
            </div>

            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Jobs</CardTitle>
                        <Video className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{totalJobs}</div>
                        <p className="text-xs text-muted-foreground">{completedJobs} completed</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
                        <PlayCircle className="h-4 w-4 text-blue-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-blue-600">{runningJobs}</div>
                        <p className="text-xs text-muted-foreground">{runningJobs > 0 ? "Generating..." : "Idle"}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Videos This Month</CardTitle>
                        <TrendingUp className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{usage?.videos_generated_this_month || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            {usage?.videos_limit === 999999 ? "Unlimited" : `${usage?.videos_limit || 0} limit`}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {totalJobs > 0 ? Math.round((completedJobs / totalJobs) * 100) : 0}%
                        </div>
                        <p className="text-xs text-muted-foreground">{failedJobs} failed</p>
                    </CardContent>
                </Card>
            </div>

            {/* Recent Jobs */}
            <Card>
                <CardHeader>
                    <CardTitle>Recent Jobs</CardTitle>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="flex items-center gap-2 text-muted-foreground py-4">
                            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                        </div>
                    ) : (
                        <div className="relative w-full overflow-auto">
                            <table className="w-full caption-bottom text-sm text-left">
                                <thead className="[&_tr]:border-b">
                                    <tr className="border-b">
                                        <th className="h-12 px-4 align-middle font-medium text-muted-foreground">Job</th>
                                        <th className="h-12 px-4 align-middle font-medium text-muted-foreground">Status</th>
                                        <th className="h-12 px-4 align-middle font-medium text-muted-foreground">Videos</th>
                                        <th className="h-12 px-4 align-middle font-medium text-muted-foreground">Created</th>
                                        <th className="h-12 px-4 align-middle font-medium text-muted-foreground">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="[&_tr:last-child]:border-0">
                                    {jobs?.map((job: any) => (
                                        <tr key={job.id} className="border-b transition-colors hover:bg-muted/50">
                                            <td className="p-4 align-middle font-medium">#{job.id}</td>
                                            <td className="p-4 align-middle">{getStatusBadge(job.status)}</td>
                                            <td className="p-4 align-middle">{job.videos_count || "–"}</td>
                                            <td className="p-4 align-middle text-sm">
                                                {new Date(job.created_at).toLocaleString()}
                                            </td>
                                            <td className="p-4 align-middle">
                                                <Link href={`/jobs/${job.id}`}>
                                                    <Button variant="outline" size="sm">View</Button>
                                                </Link>
                                            </td>
                                        </tr>
                                    ))}
                                    {!jobs?.length && (
                                        <tr>
                                            <td colSpan={5} className="p-8 text-center text-muted-foreground">
                                                No jobs yet. Start your first automation!
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
