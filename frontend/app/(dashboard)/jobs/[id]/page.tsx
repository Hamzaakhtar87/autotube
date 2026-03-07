"use client"

import { useQuery, useMutation } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Terminal, StopCircle, CheckCircle2, Loader2, Circle, ChevronDown, ChevronUp } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useToast } from "@/components/ui/use-toast"

const STAGES = [
    { key: "topic", label: "Discovering topic", icon: "🔍", pct: 10 },
    { key: "script", label: "Writing script", icon: "📝", pct: 25 },
    { key: "audio", label: "Recording voiceover", icon: "🎤", pct: 40 },
    { key: "visual", label: "Finding visuals", icon: "🎬", pct: 60 },
    { key: "render", label: "Rendering video", icon: "🎥", pct: 80 },
    { key: "metadata", label: "Generating metadata", icon: "📋", pct: 90 },
    { key: "complete", label: "Complete!", icon: "✅", pct: 100 },
]

function detectStage(logs: any[]): number {
    if (!logs || logs.length === 0) return -1
    for (let i = logs.length - 1; i >= 0; i--) {
        const msg = logs[i].message?.toLowerCase() || ""
        if (msg.includes("batch complete") || msg.includes("job finished") || msg.includes("complete!")) return 6
        if (msg.includes("step 5/6") || msg.includes("step 6/6") || msg.includes("generating metadata") || msg.includes("uploading to youtube")) return 5
        if (msg.includes("rendering final video") || msg.includes("mixing audio")) return 4
        if (msg.includes("step 4/6") || msg.includes("searching pexels") || msg.includes("preparing scene") || msg.includes("trying provider")) return 3
        if (msg.includes("step 3/6") || msg.includes("voiceover") || msg.includes("generating audio")) return 2
        if (msg.includes("step 2/6") || msg.includes("generating script") || msg.includes("phase 1/3") || msg.includes("script ready")) return 1
        if (msg.includes("step 1/6") || msg.includes("discovering topic") || msg.includes("finding trending topic") || msg.includes("starting batch")) return 0
    }
    return -1
}

export default function JobDetailPage() {
    const { id } = useParams()
    const scrollRef = useRef<HTMLDivElement>(null)
    const summaryScrollRef = useRef<HTMLDivElement>(null)
    const { toast } = useToast()
    const [showLogs, setShowLogs] = useState(false)

    const { data: job, isLoading } = useQuery({
        queryKey: ["job", id],
        queryFn: async () => {
            const res = await api.get(`/jobs/${id}`)
            return res.data
        },
        refetchInterval: (query) => {
            return query.state.data?.status === "running" ? 1500 : 5000
        }
    })

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
        if (summaryScrollRef.current) {
            summaryScrollRef.current.scrollTop = summaryScrollRef.current.scrollHeight
        }
    }, [job?.logs])

    const stopMutation = useMutation({
        mutationFn: async () => api.post(`/jobs/${id}/stop`),
        onSuccess: () => toast({ title: "Automation Stopped" }),
        onError: () => toast({ title: "Error", variant: "destructive" })
    })

    if (isLoading) return <div className="flex items-center gap-2 text-muted-foreground p-8"><Loader2 className="h-4 w-4 animate-spin" /> Loading job details...</div>

    const currentStage = detectStage(job?.logs || [])
    const isRunning = job?.status === "running" || job?.status === "pending"
    const isComplete = job?.status === "completed"
    const isFailed = job?.status === "failed"

    const statusColor = isComplete ? "text-green-600" : isFailed ? "text-red-600" : isRunning ? "text-blue-600" : "text-gray-500"
    const statusBg = isComplete ? "bg-green-100 dark:bg-green-900/30" : isFailed ? "bg-red-100 dark:bg-red-900/30" : isRunning ? "bg-blue-100 dark:bg-blue-900/30" : "bg-gray-100 dark:bg-gray-800"

    // Extract key summary from logs
    const summaryLogs = job?.logs?.filter((log: any) => {
        const m = log.message || ""
        return m.includes("✅") || m.includes("✓") || m.includes("❌") ||
            m.includes("⚠") || m.includes("🎬") || m.includes("🎤") ||
            m.includes("🔍") || m.includes("📋") || m.includes("🎥") ||
            m.includes("🎵") || m.includes("📂") || m.includes("BATCH") ||
            m.includes("SUCCESS") || m.includes("Title:") ||
            log.level === "ERROR" || log.level === "WARNING"
    }) || []

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Job #{id}</h1>
                <div className="flex items-center gap-3">
                    {isRunning && (
                        <Button variant="destructive" size="sm" onClick={() => stopMutation.mutate()} disabled={stopMutation.isPending}>
                            <StopCircle className="mr-2 h-4 w-4" />
                            {stopMutation.isPending ? "Stopping..." : "Stop"}
                        </Button>
                    )}
                    <div className={`px-3 py-1.5 rounded-full text-sm font-semibold uppercase ${statusBg} ${statusColor}`}>
                        {isRunning && <Loader2 className="h-3 w-3 inline mr-1 animate-spin" />}
                        {isComplete && <CheckCircle2 className="h-3 w-3 inline mr-1" />}
                        {job?.status}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="grid gap-6 md:grid-cols-3">

                {/* Left Column: Config + Progress */}
                <div className="md:col-span-1 space-y-4">
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Configuration</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Video Count:</span>
                                <span>{job?.config?.video_count || 7}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Test Mode:</span>
                                <span>{job?.config?.test_mode ? "Yes" : "No"}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Started:</span>
                                <span className="text-xs">{new Date(job?.created_at).toLocaleString()}</span>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Progress</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Progress Bar */}
                            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mb-4">
                                <div
                                    className={`h-2.5 rounded-full transition-all duration-700 ease-out ${isComplete ? "bg-green-500" : isFailed ? "bg-red-500" : "bg-blue-500"
                                        }`}
                                    style={{ width: `${isComplete ? 100 : isFailed ? Math.max(5, currentStage >= 0 ? STAGES[currentStage].pct : 5) : (currentStage >= 0 ? STAGES[currentStage].pct : 2)}%` }}
                                />
                            </div>

                            {/* Stage List */}
                            <div className="space-y-3">
                                {STAGES.map((stage, idx) => {
                                    const isDone = currentStage > idx || isComplete
                                    const isActive = currentStage === idx && isRunning
                                    const isPending = currentStage < idx && !isComplete

                                    return (
                                        <div key={stage.key} className={`flex items-center gap-3 text-sm transition-all ${isPending ? "opacity-40" : ""}`}>
                                            <div className="flex-shrink-0 w-6 text-center">
                                                {isDone ? (
                                                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                                                ) : isActive ? (
                                                    <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                                                ) : (
                                                    <Circle className="h-5 w-5 text-gray-300 dark:text-gray-600" />
                                                )}
                                            </div>
                                            <span className="mr-1">{stage.icon}</span>
                                            <span className={isDone ? "text-green-700 dark:text-green-400 font-medium" : isActive ? "text-blue-700 dark:text-blue-400 font-medium" : "text-muted-foreground"}>
                                                {stage.label}
                                            </span>
                                        </div>
                                    )
                                })}
                            </div>

                            {isFailed && (
                                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                                    <p className="text-sm text-red-700 dark:text-red-400 font-medium">
                                        {job?.logs?.find((l: any) => l.level === "ERROR")?.message?.slice(0, 200) || "Job failed. Check logs for details."}
                                    </p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column: Summary + Expandable Logs */}
                <div className="md:col-span-2 space-y-4">
                    {/* Summary Card — key events */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Summary</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {summaryLogs.length === 0 ? (
                                <p className="text-sm text-muted-foreground italic">
                                    {isRunning ? "Waiting for updates..." : "No events recorded."}
                                </p>
                            ) : (
                                <div ref={summaryScrollRef} className="space-y-1.5 max-h-[300px] overflow-auto pr-2">
                                    {summaryLogs.map((log: any, i: number) => (
                                        <div key={i} className="text-sm break-all">
                                            <span className="text-muted-foreground text-xs mr-2">
                                                {new Date(log.timestamp).toLocaleTimeString()}
                                            </span>
                                            <span className={
                                                log.level === "ERROR" ? "text-red-600 dark:text-red-400" :
                                                    log.level === "WARNING" ? "text-yellow-600 dark:text-yellow-400" :
                                                        log.message?.includes("✅") ? "text-green-600 dark:text-green-400" :
                                                            ""
                                            }>
                                                {log.message}
                                            </span>
                                        </div>
                                    ))}
                                    {isRunning && <div className="animate-pulse text-blue-500 text-sm mt-1">Processing...</div>}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Completion/Output Card */}
                    {isComplete && (
                        <Card className="border-green-200 dark:border-green-900 bg-green-50/50 dark:bg-green-900/10">
                            <CardHeader className="pb-3 flex flex-row items-center justify-between">
                                <CardTitle className="text-base text-green-800 dark:text-green-400">
                                    <CheckCircle2 className="h-5 w-5 inline mr-2" />
                                    Automation Complete
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm">
                                    The video has been successfully generated.
                                </p>

                                {(() => {
                                    const mp4Log = job?.logs?.find((l: any) => l.message?.includes(".mp4") && (l.message?.includes("output_v2") || l.message?.includes("Video saved:")))?.message || ""
                                    const match = mp4Log.match(/output_v2\/([^ ]+\.mp4)/)
                                    const filename = match ? match[1] : null;

                                    if (filename) {
                                        const downloadUrl = `${process.env.NEXT_PUBLIC_API_URL || 'https://autotube-api-oave.onrender.com'}/output/${filename}`;
                                        return (
                                            <div className="mt-4">
                                                <a href={downloadUrl} target="_blank" rel="noreferrer" download>
                                                    <Button className="w-full sm:w-auto bg-green-600 hover:bg-green-700 text-white">
                                                        ⬇️ Download Video
                                                    </Button>
                                                </a>
                                            </div>
                                        )
                                    }

                                    return (
                                        <p className="text-sm mt-2 text-muted-foreground break-all">
                                            {(job?.logs?.find((l: any) => l.message?.includes("Video saved:"))?.message || "") ||
                                                (job?.logs?.find((l: any) => l.message?.includes("YouTube"))?.message || "") ||
                                                "Check the summary above for the final file path or upload link."}
                                        </p>
                                    )
                                })()}
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    )
}
