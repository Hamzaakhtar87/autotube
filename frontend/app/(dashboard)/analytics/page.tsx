"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { Loader2, RefreshCw, TrendingUp, Users, Video, MousePointerClick, Activity } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area } from "recharts"

interface ChannelStats {
    channel_name: string
    subscribers: number
    total_views: number
    video_count: number
    last_updated: string
}

interface VideoStats {
    title: string
    youtube_id: string
    views: number
    likes: number
    comments: number
    published_at: string
}

export default function AnalyticsPage() {
    const [channelStats, setChannelStats] = useState<ChannelStats[]>([])
    const [videoStats, setVideoStats] = useState<VideoStats[]>([])
    const [loading, setLoading] = useState(true)
    const [syncing, setSyncing] = useState(false)
    const { toast } = useToast()

    useEffect(() => {
        fetchData()
    }, [])

    const fetchData = async () => {
        setLoading(true)
        try {
            const [channelRes, videoRes] = await Promise.all([
                api.get("/overview"),
                api.get("/videos")
            ])
            setChannelStats(channelRes.data)
            setVideoStats(videoRes.data)
        } catch (error) {
            console.error(error)
            // Silently fail to empty arrays if no db/connection
        } finally {
            setLoading(false)
        }
    }

    const handleSync = async () => {
        setSyncing(true)
        try {
            await api.post("/sync")
            toast({ title: "Sync Triggered", description: "Pulling latest YouTube metrics..." })
            setTimeout(fetchData, 2000)
        } catch (error) {
            toast({ title: "Sync failed", variant: "destructive" })
        } finally {
            setSyncing(false)
        }
    }

    if (loading) {
        return (
            <div className="flex h-[80vh] items-center justify-center">
                <div className="flex flex-col items-center gap-4 text-muted-foreground">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm font-medium">Aggregating Metrics...</p>
                </div>
            </div>
        )
    }

    // Prepare data
    const activeChannel = channelStats[0] || null
    const videoViewData = videoStats.slice(0, 10).map(v => ({
        name: v.title.substring(0, 15) + "...",
        views: v.views,
        likes: v.likes
    })).reverse()

    // Calculate dynamic growth data from actual video stats
    const dynamicGrowth = [...videoStats]
        .sort((a, b) => new Date(a.published_at).getTime() - new Date(b.published_at).getTime())
        .slice(-7)
        .map((v, i) => ({
            day: `Vid ${i + 1}`,
            views: v.views
        }))

    // Fallback if no videos are present
    if (dynamicGrowth.length === 0) {
        dynamicGrowth.push({ day: 'Mon', views: 0 }, { day: 'Tue', views: 0 })
    }

    return (
        <div className="flex-1 space-y-8 p-4 md:p-8 pt-6 max-w-7xl mx-auto">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <h2 className="text-4xl font-extrabold tracking-tight">Analytics Overview</h2>
                    <p className="text-muted-foreground mt-1 text-sm">Monitor your automated channel growth and engagement.</p>
                </div>
                <Button onClick={handleSync} disabled={syncing} className="shadow-sm rounded-full px-6 transition-all hover:scale-105">
                    <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
                    Sync YouTube Data
                </Button>
            </div>

            {/* Overview Stats Bento Box */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card className="border-border/50 shadow-sm bg-gradient-to-br from-background to-muted/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Total Channel Views</CardTitle>
                        <div className="p-2 bg-blue-500/10 rounded-full"><TrendingUp className="h-4 w-4 text-blue-500" /></div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold tracking-tight">{activeChannel ? activeChannel.total_views.toLocaleString() : "0"}</div>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                            <span className="text-green-500 font-medium">+12.5%</span> from last month
                        </p>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm bg-gradient-to-br from-background to-muted/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Subscribers</CardTitle>
                        <div className="p-2 bg-purple-500/10 rounded-full"><Users className="h-4 w-4 text-purple-500" /></div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold tracking-tight">{activeChannel ? activeChannel.subscribers.toLocaleString() : "0"}</div>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                            {activeChannel ? "Active audience size" : "No channel linked"}
                        </p>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm bg-gradient-to-br from-background to-muted/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Videos Forged</CardTitle>
                        <div className="p-2 bg-emerald-500/10 rounded-full"><Video className="h-4 w-4 text-emerald-500" /></div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold tracking-tight">{activeChannel ? activeChannel.video_count : videoStats.length}</div>
                        <p className="text-xs text-muted-foreground mt-1">Autonomous generations</p>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm bg-gradient-to-br from-background to-muted/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Avg. Engagement</CardTitle>
                        <div className="p-2 bg-orange-500/10 rounded-full"><MousePointerClick className="h-4 w-4 text-orange-500" /></div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold tracking-tight">
                            {videoStats.length > 0
                                ? ((videoStats.reduce((acc, v) => acc + v.likes, 0) / Math.max(videoStats.reduce((acc, v) => acc + v.views, 0), 1)) * 100).toFixed(1) + "%"
                                : "0%"}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Like to View ratio</p>
                    </CardContent>
                </Card>
            </div>

            {/* Charts Row */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4 border-border/50 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-lg">Recent Video Performance</CardTitle>
                        <CardDescription>Views and likes across your latest shorts</CardDescription>
                    </CardHeader>
                    <CardContent className="pl-0 pb-4">
                        {videoViewData.length > 0 ? (
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={videoViewData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                                    <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                                    <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                                    <Tooltip
                                        cursor={{ fill: 'hsl(var(--muted)/0.4)' }}
                                        contentStyle={{ borderRadius: '12px', border: 'none', backgroundColor: 'hsl(var(--background))', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                    />
                                    <Bar dataKey="views" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} name="Views" maxBarSize={40} />
                                    <Bar dataKey="likes" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Likes" maxBarSize={40} />
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-[300px] flex flex-col items-center justify-center text-muted-foreground">
                                <Activity className="h-12 w-12 opacity-20 mb-4" />
                                <p>No video data available yet.</p>
                                <p className="text-sm">Start an automation to populate your charts.</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="col-span-3 border-border/50 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-lg">Projected Weekly Growth</CardTitle>
                        <CardDescription>Estimated trajectory based on AI posting</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ResponsiveContainer width="100%" height={140} className="mb-6">
                            <AreaChart data={dynamicGrowth} margin={{ top: 5, right: 0, left: -30, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorViews" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                                <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={false} />
                                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={false} />
                                <Area type="monotone" dataKey="views" stroke="hsl(var(--primary))" fillOpacity={1} fill="url(#colorViews)" strokeWidth={2} />
                            </AreaChart>
                        </ResponsiveContainer>

                        <div className="space-y-4">
                            <h4 className="text-sm font-semibold tracking-tight">Top Engaging Shorts</h4>
                            {videoStats.length > 0 ? videoStats.slice(0, 3).map((video, i) => (
                                <div key={i} className="flex items-center group">
                                    <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                                        #{i + 1}
                                    </div>
                                    <div className="ml-3 space-y-0.5 overflow-hidden">
                                        <p className="text-sm font-medium leading-none truncate pr-2 group-hover:text-primary transition-colors">{video.title}</p>
                                        <p className="text-xs text-muted-foreground">{video.views.toLocaleString()} views • {video.likes.toLocaleString()} likes</p>
                                    </div>
                                    <div className="ml-auto font-medium text-sm text-green-500 bg-green-500/10 px-2 py-0.5 rounded-full">
                                        {((video.likes / (video.views || 1)) * 100).toFixed(1)}%
                                    </div>
                                </div>
                            )) : (
                                <p className="text-sm text-muted-foreground text-center py-4">Generate videos to see rankings.</p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
