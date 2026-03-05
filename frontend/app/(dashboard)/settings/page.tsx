/* eslint-disable @next/next/no-img-element */
"use client"

import { useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { useToast } from "@/components/ui/use-toast"
import { useTheme } from "next-themes"
import {
    CheckCircle, Youtube, ShieldAlert,
    User, Crown, Mail, Upload, Moon, Sun, Monitor, Key, Lock
} from "lucide-react"
import { Input } from "@/components/ui/input"

export default function SettingsPage() {
    const { toast } = useToast()
    const queryClient = useQueryClient()
    const { theme, setTheme } = useTheme()
    const fileInputRef = useRef<HTMLInputElement>(null)
    const [avatarUrl, setAvatarUrl] = useState<string | null>(null)

    // Password change state
    const [currentPassword, setCurrentPassword] = useState("")
    const [newPassword, setNewPassword] = useState("")

    useEffect(() => {
        const saved = localStorage.getItem("user_avatar")
        if (saved) setAvatarUrl(saved)
    }, [])

    const { data: status, refetch, isLoading, isError } = useQuery({
        queryKey: ["config_status"],
        queryFn: async () => {
            const res = await api.get("/config/status")
            return res.data
        },
        retry: 1
    })

    const { data: profile } = useQuery({
        queryKey: ["profile"],
        queryFn: async () => {
            try {
                const res = await api.get("/config/profile")
                return res.data
            } catch { return null }
        },
        retry: 0
    })

    const [secretsJson, setSecretsJson] = useState("")
    const secretsMutation = useMutation({
        mutationFn: (data: any) => api.post("/config/secrets", JSON.parse(data)),
        onSuccess: () => { toast({ title: "Configuration Updated" }); setSecretsJson(""); refetch() },
        onError: () => toast({ title: "Invalid Configuration", variant: "destructive" })
    })

    const passwordMutation = useMutation({
        mutationFn: async () => api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword }),
        onSuccess: () => {
            toast({ title: "Password Updated", description: "Successfully changed password." })
            setCurrentPassword("")
            setNewPassword("")
        },
        onError: (err: any) => toast({
            title: "Password Change Failed",
            variant: "destructive",
            description: err.response?.data?.detail || "An error occurred."
        })
    })

    const handleConnect = async () => {
        try {
            const res = await api.get("/auth/youtube/url")
            window.location.href = res.data.url
        } catch {
            toast({ title: "Connection Failed", variant: "destructive", description: "System configuration missing." })
        }
    }

    const disconnectMutation = useMutation({
        mutationFn: async () => api.post("/auth/youtube/disconnect"),
        onSuccess: () => { toast({ title: "Disconnected" }); refetch() },
        onError: () => toast({ title: "Failed", variant: "destructive" })
    })

    const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            const reader = new FileReader()
            reader.onloadend = () => {
                const result = reader.result as string
                setAvatarUrl(result)
                localStorage.setItem("user_avatar", result)
                toast({
                    title: "Avatar Uploaded",
                    description: "Your new avatar has been successfully uploaded."
                })
            }
            reader.readAsDataURL(file)
        }
    }

    const tierColors: Record<string, string> = {
        free: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        pro: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
        enterprise: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    }

    return (
        <div className="space-y-6 max-w-4xl max-h-[calc(100vh-100px)] pb-10">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
                <p className="text-muted-foreground mt-1">Manage your account profile and integrations.</p>
            </div>

            <div className="grid gap-6">

                {/* ═══ PROFILE CARD ═══ */}
                {profile && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <User className="h-5 w-5 text-indigo-500" />
                                Account Profile
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
                                {/* Avatar Upload Area */}
                                <div className="relative group cursor-pointer" onClick={() => fileInputRef.current?.click()}>
                                    {avatarUrl ? (
                                        <img src={avatarUrl} alt="Avatar" className="h-20 w-20 rounded-full object-cover shadow-sm transition-all group-hover:opacity-80" />
                                    ) : (
                                        <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-3xl font-bold shadow-sm transition-all group-hover:opacity-80">
                                            {(profile.full_name || profile.email || "U").charAt(0).toUpperCase()}
                                        </div>
                                    )}
                                    <div className="absolute inset-0 bg-black/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Upload className="h-6 w-6 text-white" />
                                    </div>
                                    <input
                                        type="file"
                                        className="hidden"
                                        ref={fileInputRef}
                                        accept="image/png, image/jpeg"
                                        onChange={handleAvatarUpload}
                                    />
                                </div>

                                <div className="space-y-1">
                                    <h3 className="text-xl font-semibold">{profile.full_name || "User"}</h3>
                                    <p className="text-sm text-muted-foreground flex items-center gap-2">
                                        <Mail className="h-4 w-4" /> {profile.email}
                                    </p>
                                    <div className="flex items-center gap-3 mt-2">
                                        <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${tierColors[profile.subscription_tier] || tierColors.free}`}>
                                            <Crown className="h-3 w-3 inline mr-1" />
                                            {(profile.subscription_tier || "free").toUpperCase()} TIER
                                        </span>
                                        <span className="text-sm text-muted-foreground font-medium">
                                            {profile.videos_generated_this_month} videos forged this month
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* ═══ PASSWORD CHANGE ═══ */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Lock className="h-5 w-5 text-slate-500" /> Account Security
                        </CardTitle>
                        <CardDescription>Update your password to keep your account secure.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 max-w-sm">
                        <div className="space-y-2">
                            <Label>Current Password</Label>
                            <Input
                                type="password"
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>New Password</Label>
                            <Input
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                            />
                        </div>
                        <Button
                            onClick={() => passwordMutation.mutate()}
                            disabled={!currentPassword || newPassword.length < 8 || passwordMutation.isPending}
                        >
                            {passwordMutation.isPending ? "Updating..." : "Update Password"}
                        </Button>
                    </CardContent>
                </Card>

                {/* ═══ THEME SETTINGS ═══ */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Moon className="h-5 w-5 text-slate-500" /> Interface Theme
                        </CardTitle>
                        <CardDescription>Select your preferred visual aesthetic.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex gap-4">
                            <Button
                                variant={theme === "light" ? "default" : "outline"}
                                onClick={() => setTheme("light")}
                                className="w-32"
                            >
                                <Sun className="mr-2 h-4 w-4" /> Light
                            </Button>
                            <Button
                                variant={theme === "dark" ? "default" : "outline"}
                                onClick={() => setTheme("dark")}
                                className="w-32"
                            >
                                <Moon className="mr-2 h-4 w-4" /> Dark
                            </Button>
                            <Button
                                variant={theme === "system" ? "default" : "outline"}
                                onClick={() => setTheme("system")}
                                className="w-32"
                            >
                                <Monitor className="mr-2 h-4 w-4" /> System
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* ═══ YOUTUBE CONNECTION ═══ */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 font-semibold">
                            <Youtube className="text-red-500 h-6 w-6" /> YouTube Output Integration
                        </CardTitle>
                        <CardDescription>Link your channel to enable autonomous publishing.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {status?.has_credentials ? (
                            <div className="rounded-xl bg-green-500/10 p-5 border border-green-500/20">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <div className="bg-green-500/20 p-2.5 rounded-full">
                                            <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-green-900 dark:text-green-100">Channel Linked & Authorized</h3>
                                            <p className="text-sm text-green-700 dark:text-green-300">Agent has permission to generate and upload.</p>
                                        </div>
                                    </div>
                                    <Button variant="destructive" size="sm" disabled={disconnectMutation.isPending} onClick={() => disconnectMutation.mutate()}>
                                        {disconnectMutation.isPending ? "Disconnecting..." : "Disconnect"}
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            <div className="rounded-xl bg-muted/40 p-6 border border-dashed border-muted-foreground/30">
                                <div className="flex flex-col items-center justify-center text-center space-y-4">
                                    <div className="p-4 bg-red-500/10 rounded-full"><Youtube className="h-8 w-8 text-red-500" /></div>
                                    <div>
                                        <h3 className="font-semibold text-lg">No Output Channel Linked</h3>
                                        <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1">Connect your YouTube account to publish shorts automatically after rendering.</p>
                                    </div>
                                    <Button className="bg-red-600 hover:bg-red-700 text-white shadow-sm h-11 px-8" onClick={handleConnect} disabled={!status?.has_client_secrets}>
                                        Link YouTube Channel
                                    </Button>
                                    {isLoading && <p className="text-xs text-muted-foreground">Verifying status...</p>}
                                    {isError && <p className="text-xs text-red-500">Security check failed.</p>}
                                    {!isLoading && !isError && !status?.has_client_secrets && (
                                        <p className="text-xs text-orange-500 font-medium bg-orange-500/10 px-3 py-1.5 rounded-md mt-2">
                                            Admin Configuration Required: Missing OAuth Client Secrets.
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* ═══ ADMIN CONFIG — Only visible to admins ═══ */}
                {status?.is_admin && (
                    <Card className="border-orange-500/30 bg-orange-500/5 overflow-hidden">
                        <CardHeader className="bg-orange-500/10 pb-4">
                            <CardTitle className="text-orange-600 flex items-center gap-2 text-lg">
                                <ShieldAlert className="h-5 w-5" /> Owner Configuration Node
                            </CardTitle>
                            <CardDescription className="text-orange-700/70 dark:text-orange-400/70">
                                Deploy exact `client_secrets.json` from GCP API Console.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4 pt-4">
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <Label className="font-semibold text-orange-900/80 dark:text-orange-100/80">OAuth 2.0 Client Vault</Label>
                                    {status?.has_client_secrets && <span className="text-xs bg-green-500/20 text-green-700 font-bold px-2 py-1 rounded">✓ Armed</span>}
                                </div>
                                <textarea
                                    className="w-full min-h-[120px] p-3 border-orange-500/30 rounded-md text-xs font-mono bg-background/50 focus:ring-orange-500/50"
                                    placeholder='{"web":{"client_id":"...","project_id":"..."}}'
                                    value={secretsJson}
                                    onChange={(e) => setSecretsJson(e.target.value)}
                                />
                                <div className="flex justify-end">
                                    <Button className="bg-orange-600 hover:bg-orange-700 text-white" onClick={() => secretsMutation.mutate(secretsJson)} disabled={!secretsJson || secretsMutation.isPending}>
                                        Force Update Logic
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    )
}
