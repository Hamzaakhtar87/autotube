"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/components/ui/use-toast"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import {
    Zap, Mic, Video, Settings2, Sparkles, Music, Volume2,
    MonitorPlay, Smartphone, Upload, Clock, Download,
    Palette, MessageSquare, ChevronDown, ChevronUp, Pen
} from "lucide-react"

const VOICE_OPTIONS = [
    { value: "en-US-GuyNeural", label: "Guy (Male, US)" },
    { value: "en-US-JennyNeural", label: "Jenny (Female, US)" },
    { value: "en-US-AriaNeural", label: "Aria (Female, US)" },
    { value: "en-US-DavisNeural", label: "Davis (Male, US)" },
    { value: "en-GB-RyanNeural", label: "Ryan (Male, UK)" },
    { value: "en-GB-SoniaNeural", label: "Sonia (Female, UK)" }
]

const NICHE_OPTIONS = [
    { value: "psychology", label: "Psychology & Human Behavior" },
    { value: "science", label: "Science & Technology" },
    { value: "finance", label: "Finance & Money" },
    { value: "self_improvement", label: "Self Improvement" },
    { value: "history", label: "History & Facts" },
    { value: "health", label: "Health & Wellness" },
    { value: "mixed", label: "Mixed / Trending" }
]

const MUSIC_OPTIONS = [
    { value: "random", label: "Variety of Non-Copyright Sounds (Archive.org API)" },
    { value: "none", label: "No Background Music" }
]

const STYLE_OPTIONS = [
    { value: "narration", label: "🎙️ Narration" },
    { value: "what_if", label: "🤔 What-If Scenarios" },
    { value: "explainer", label: "📖 Explainer" },
    { value: "listicle", label: "📋 Listicle / Top N" },
    { value: "documentary", label: "🎬 Documentary" },
]

const TONE_OPTIONS = [
    { value: "serious", label: "Serious & Intellectual" },
    { value: "casual", label: "Casual & Friendly" },
    { value: "dramatic", label: "Dramatic & Suspenseful" },
    { value: "educational", label: "Educational & Clear" },
    { value: "humorous", label: "Witty & Humorous" },
]

export default function CreateJobPage() {
    const router = useRouter()
    const { toast } = useToast()

    // Core settings
    const [videoFormat, setVideoFormat] = useState("short")
    const [videoCount, setVideoCount] = useState(1)
    const [voice, setVoice] = useState(VOICE_OPTIONS[1].value)
    const [niche, setNiche] = useState(NICHE_OPTIONS[3].value)
    const [bgMusic, setBgMusic] = useState<string>("random")
    const [bgMusicVolume, setBgMusicVolume] = useState<number>(15)

    // Creative Brief (collapsible)
    const [showCreativeBrief, setShowCreativeBrief] = useState(false)
    const [customTopic, setCustomTopic] = useState("")
    const [customNiche, setCustomNiche] = useState("")
    const [channelStyle, setChannelStyle] = useState("narration")
    const [tone, setTone] = useState("serious")

    // Output Action
    const [outputAction, setOutputAction] = useState("generate_only")
    const [scheduleDatetime, setScheduleDatetime] = useState("")

    // Load user preferences
    const { data: preferences } = useQuery({
        queryKey: ["user_preferences"],
        queryFn: async () => {
            const res = await api.get("/config/preferences")
            return res.data
        },
        retry: 0
    })

    useEffect(() => {
        if (preferences) {
            if (preferences.default_video_count) setVideoCount(preferences.default_video_count)
            if (preferences.voice) setVoice(preferences.voice)
            if (preferences.niche) setNiche(preferences.niche)
            if (preferences.video_format) setVideoFormat(preferences.video_format)
            if (preferences.channel_style) setChannelStyle(preferences.channel_style)
            if (preferences.tone) setTone(preferences.tone)
            if (preferences.output_action) setOutputAction(preferences.output_action)
            if (preferences.custom_topic) setCustomTopic(preferences.custom_topic)
            if (preferences.custom_niche) setCustomNiche(preferences.custom_niche)
            if (preferences.bg_music !== undefined) {
                if (preferences.bg_music === true) setBgMusic("random");
                else if (preferences.bg_music === false) setBgMusic("none");
                else setBgMusic(String(preferences.bg_music));
            }
            if (preferences.bg_music_volume !== undefined) {
                setBgMusicVolume(Math.round(preferences.bg_music_volume * 100))
            }
        }
    }, [preferences])

    const startJobMutation = useMutation({
        mutationFn: async () => {
            // Save preferences
            await api.post("/config/preferences", {
                voice,
                niche,
                bg_music: bgMusic,
                bg_music_volume: bgMusicVolume / 100.0,
                default_video_count: videoCount,
                video_format: videoFormat,
                custom_topic: customTopic,
                custom_niche: customNiche,
                channel_style: channelStyle,
                tone,
                output_action: outputAction,
                schedule_datetime: scheduleDatetime,
            })

            // Start job
            return api.post("/jobs", {
                test_mode: outputAction === "generate_only",
                videos_count: videoCount,
                output_action: outputAction,
                video_format: videoFormat,
                schedule_datetime: scheduleDatetime,
            })
        },
        onSuccess: (data) => {
            toast({ title: "🚀 Automation Started", description: `Job #${data.data.id} created.` })
            router.push(`/jobs/${data.data.id}`)
        },
        onError: (error: any) => {
            const msg = error?.response?.data?.detail || "Failed to start automation."
            toast({ title: "Error", description: msg, variant: "destructive" })
        }
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        startJobMutation.mutate()
    }

    return (
        <div className="max-w-3xl mx-auto w-full space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">New Automation</h1>

            {/* ─── VIDEO FORMAT SELECTOR ─── */}
            <Card className="border-border/40 shadow-sm">
                <CardContent className="pt-6">
                    <Label className="flex items-center gap-2 font-semibold mb-4">
                        <MonitorPlay className="h-4 w-4 text-cyan-500" />
                        Video Format
                    </Label>
                    <div className="grid grid-cols-2 gap-3">
                        <button
                            type="button"
                            onClick={() => setVideoFormat("short")}
                            className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${videoFormat === "short"
                                ? "border-primary bg-primary/5 shadow-md"
                                : "border-border/50 hover:border-border"
                                }`}
                        >
                            <Smartphone className={`h-8 w-8 ${videoFormat === "short" ? "text-primary" : "text-muted-foreground"}`} />
                            <div className="text-center">
                                <p className="font-semibold text-sm">Short (9:16)</p>
                                <p className="text-[10px] text-muted-foreground">40-60s • YouTube Shorts, TikTok, Reels</p>
                            </div>
                            {videoFormat === "short" && (
                                <div className="absolute top-2 right-2 h-2 w-2 rounded-full bg-primary animate-pulse" />
                            )}
                        </button>
                        <button
                            type="button"
                            onClick={() => setVideoFormat("long")}
                            className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${videoFormat === "long"
                                ? "border-primary bg-primary/5 shadow-md"
                                : "border-border/50 hover:border-border"
                                }`}
                        >
                            <MonitorPlay className={`h-8 w-8 ${videoFormat === "long" ? "text-primary" : "text-muted-foreground"}`} />
                            <div className="text-center">
                                <p className="font-semibold text-sm">Long (16:9)</p>
                                <p className="text-[10px] text-muted-foreground">3-5 min • Standard YouTube Videos</p>
                            </div>
                            {videoFormat === "long" && (
                                <div className="absolute top-2 right-2 h-2 w-2 rounded-full bg-primary animate-pulse" />
                            )}
                        </button>
                    </div>
                </CardContent>
            </Card>

            {/* ─── CORE SETTINGS ─── */}
            <Card className="border-border/40 shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings2 className="h-5 w-5 text-primary" />
                        Generation Settings
                    </CardTitle>
                    <CardDescription>
                        Configure your AI video parameters before starting the rendering engine.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {/* LEFT COL */}
                        <div className="space-y-6">
                            {/* Niche Selector */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <Sparkles className="h-4 w-4 text-purple-500" />
                                    Content Niche
                                </Label>
                                <Select value={niche} onValueChange={setNiche}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select content topic..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {NICHE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <p className="text-xs text-muted-foreground">
                                    The AI agent will analyze recent trends matching this category.
                                </p>
                            </div>

                            {/* Voice Selector */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <Mic className="h-4 w-4 text-blue-500" />
                                    AI Narrator Voice
                                </Label>
                                <Select value={voice} onValueChange={setVoice}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a voice..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {VOICE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* RIGHT COL */}
                        <div className="space-y-6">
                            {/* Video Count */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <Video className="h-4 w-4 text-emerald-500" />
                                    Videos to Generate
                                </Label>
                                <Input
                                    type="number"
                                    min={1}
                                    max={videoFormat === "long" ? 3 : 10}
                                    value={videoCount}
                                    onChange={(e) => setVideoCount(parseInt(e.target.value) || 1)}
                                    className="max-w-full"
                                />
                                <p className="text-xs text-muted-foreground">
                                    {videoFormat === "long"
                                        ? `${videoCount} long-form video${videoCount > 1 ? "s" : ""} (3-5 min each).`
                                        : `${videoCount} short${videoCount > 1 ? "s" : ""} (40-60s each).`}
                                </p>
                            </div>

                            {/* Background Music */}
                            <div className="space-y-4 pt-2">
                                <div className="space-y-4 pt-4 border-t border-border/50">
                                    <Label className="flex items-center gap-2 font-semibold">
                                        <Music className="h-4 w-4 text-pink-500" />
                                        Background Music
                                    </Label>
                                    <Select value={bgMusic} onValueChange={setBgMusic}>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select background music..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {MUSIC_OPTIONS.map((opt) => (
                                                <SelectItem key={opt.value} value={opt.value}>
                                                    {opt.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>

                                    {bgMusic !== "none" && (
                                        <div className="space-y-3 pt-2">
                                            <div className="flex items-center justify-between">
                                                <Label className="flex items-center gap-2 text-muted-foreground text-sm">
                                                    <Volume2 className="h-4 w-4" />
                                                    Volume Level
                                                </Label>
                                                <span className="text-xs font-semibold text-pink-500">{bgMusicVolume}%</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="0"
                                                max="100"
                                                value={bgMusicVolume}
                                                onChange={(e) => setBgMusicVolume(parseInt(e.target.value) || 0)}
                                                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-pink-500"
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* ─── CREATIVE BRIEF (Collapsible) ─── */}
            <Card className="border-border/40 shadow-sm">
                <CardHeader
                    className="cursor-pointer select-none"
                    onClick={() => setShowCreativeBrief(!showCreativeBrief)}
                >
                    <CardTitle className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                            <Pen className="h-5 w-5 text-amber-500" />
                            Creative Brief
                            <span className="text-xs font-normal text-muted-foreground ml-1">(Optional)</span>
                        </span>
                        {showCreativeBrief
                            ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </CardTitle>
                    <CardDescription>
                        Customize the topic, style, and tone to match your channel identity.
                    </CardDescription>
                </CardHeader>
                {showCreativeBrief && (
                    <CardContent className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Custom Topic */}
                            <div className="space-y-3 md:col-span-2">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <MessageSquare className="h-4 w-4 text-orange-500" />
                                    Custom Topic
                                </Label>
                                <Input
                                    placeholder="e.g. 'Why sleep deprivation destroys your brain' — leave empty for AI discovery"
                                    value={customTopic}
                                    onChange={(e) => setCustomTopic(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    If set, the AI will skip trend discovery and create a video about this exact topic.
                                </p>
                            </div>

                            {/* Custom Niche */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <Sparkles className="h-4 w-4 text-violet-500" />
                                    Custom Niche Description
                                </Label>
                                <Input
                                    placeholder="e.g. 'Crypto DeFi for beginners'"
                                    value={customNiche}
                                    onChange={(e) => setCustomNiche(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    More specific than the dropdown — describe your exact niche.
                                </p>
                            </div>

                            {/* Channel Style */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <Palette className="h-4 w-4 text-teal-500" />
                                    Channel Style
                                </Label>
                                <Select value={channelStyle} onValueChange={setChannelStyle}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {STYLE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Tone */}
                            <div className="space-y-3">
                                <Label className="flex items-center gap-2 font-semibold">
                                    <MessageSquare className="h-4 w-4 text-rose-500" />
                                    Tone
                                </Label>
                                <Select value={tone} onValueChange={setTone}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {TONE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </CardContent>
                )}
            </Card>

            {/* ─── OUTPUT ACTION ─── */}
            <Card className="border-border/40 shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Upload className="h-5 w-5 text-green-500" />
                        Output Action
                    </CardTitle>
                    <CardDescription>
                        Choose what happens after your video is generated.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {/* Generate Only */}
                        <button
                            type="button"
                            onClick={() => setOutputAction("generate_only")}
                            className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${outputAction === "generate_only"
                                ? "border-blue-500 bg-blue-500/5 shadow-md"
                                : "border-border/50 hover:border-border"
                                }`}
                        >
                            <Download className={`h-6 w-6 ${outputAction === "generate_only" ? "text-blue-500" : "text-muted-foreground"}`} />
                            <p className="font-semibold text-sm">Generate Only</p>
                            <p className="text-[10px] text-muted-foreground text-center">Create video & download. No upload.</p>
                        </button>

                        {/* Auto Publish */}
                        <button
                            type="button"
                            onClick={() => setOutputAction("auto_publish")}
                            className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${outputAction === "auto_publish"
                                ? "border-green-500 bg-green-500/5 shadow-md"
                                : "border-border/50 hover:border-border"
                                }`}
                        >
                            <Upload className={`h-6 w-6 ${outputAction === "auto_publish" ? "text-green-500" : "text-muted-foreground"}`} />
                            <p className="font-semibold text-sm">Auto Publish</p>
                            <p className="text-[10px] text-muted-foreground text-center">Generate & upload to YouTube immediately.</p>
                        </button>

                        {/* Schedule */}
                        <button
                            type="button"
                            onClick={() => setOutputAction("schedule")}
                            className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 ${outputAction === "schedule"
                                ? "border-amber-500 bg-amber-500/5 shadow-md"
                                : "border-border/50 hover:border-border"
                                }`}
                        >
                            <Clock className={`h-6 w-6 ${outputAction === "schedule" ? "text-amber-500" : "text-muted-foreground"}`} />
                            <p className="font-semibold text-sm">Schedule</p>
                            <p className="text-[10px] text-muted-foreground text-center">Generate & schedule for a specific date/time.</p>
                        </button>
                    </div>

                    {/* Schedule DateTime picker */}
                    {outputAction === "schedule" && (
                        <div className="space-y-3 pt-3 border-t border-border/50">
                            <Label className="flex items-center gap-2 font-semibold">
                                <Clock className="h-4 w-4 text-amber-500" />
                                Schedule Date & Time
                            </Label>
                            <Input
                                type="datetime-local"
                                value={scheduleDatetime}
                                onChange={(e) => setScheduleDatetime(e.target.value)}
                                className="max-w-xs"
                                min={new Date().toISOString().slice(0, 16)}
                            />
                            <p className="text-xs text-muted-foreground">
                                The video will be uploaded to YouTube at this scheduled time.
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ─── SUBMIT ─── */}
            <Card className="border-border/40 shadow-sm">
                <CardFooter className="pt-6 pb-6">
                    <Button
                        className="w-full h-12 text-md transition-all font-semibold shadow-sm"
                        onClick={handleSubmit}
                        disabled={startJobMutation.isPending || (outputAction === "schedule" && !scheduleDatetime)}
                    >
                        <Zap className="h-5 w-5 mr-2" />
                        {startJobMutation.isPending
                            ? "Initializing Agent Engine..."
                            : outputAction === "generate_only"
                                ? `Forge ${videoCount} Video${videoCount > 1 ? "s" : ""}`
                                : outputAction === "auto_publish"
                                    ? `Forge & Publish ${videoCount} Video${videoCount > 1 ? "s" : ""}`
                                    : `Forge & Schedule ${videoCount} Video${videoCount > 1 ? "s" : ""}`}
                    </Button>
                </CardFooter>
            </Card>
        </div>
    )
}
