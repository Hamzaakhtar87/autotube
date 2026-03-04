"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/components/ui/use-toast"
import { Check, Loader2, CreditCard, Zap, Crown, ArrowRight } from "lucide-react"

export default function BillingPage() {
    const [actionLoading, setActionLoading] = useState(false)
    const searchParams = useSearchParams()
    const { toast } = useToast()

    const { data: usage, isLoading: usageLoading } = useQuery({
        queryKey: ["usage"],
        queryFn: async () => {
            const res = await api.get("/usage")
            return res.data
        },
        retry: 1
    })

    const { data: subStatus } = useQuery({
        queryKey: ["subscription"],
        queryFn: async () => {
            try {
                const res = await api.get("/billing/subscription")
                return res.data
            } catch {
                return null
            }
        },
        retry: 0
    })

    useEffect(() => {
        if (searchParams.get("success")) {
            toast({ title: "Subscription Authorized", description: "Your plan has been successfully upgraded." })
        }
        if (searchParams.get("canceled")) {
            toast({ title: "Checkout Cancelled", description: "No charges were made.", variant: "destructive" })
        }
    }, [searchParams, toast])

    const currentTier = subStatus?.tier || usage?.subscription_tier || "free"
    const isActive = currentTier !== "free"

    const handleUpgrade = async (tier: string) => {
        setActionLoading(true)
        try {
            const res = await api.post("/billing/create-checkout-session", { tier })
            window.location.href = res.data.url
        } catch {
            toast({ title: "Store Offline", description: "Lemon Squeezy integration is currently inactive.", variant: "destructive" })
            setActionLoading(false)
        }
    }

    const handleManageSubscription = async () => {
        setActionLoading(true)
        try {
            const res = await api.post("/billing/create-portal-session")
            // A portal URL redirects securely to their lemonsqueezy dashboard hub
            window.location.href = res.data.url
        } catch {
            toast({ title: "Store Offline", description: "Customer portal is temporarily unavailable.", variant: "destructive" })
            setActionLoading(false)
        }
    }

    if (usageLoading) {
        return <div className="flex h-[80vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
    }

    const limit = usage?.videos_limit
    const limitDisplay = limit === 999999 || limit === Infinity ? "Unlimited" : limit
    const isUnlimited = limit === 999999 || limit === Infinity
    const progress = !isUnlimited && limit
        ? Math.min(100, ((usage?.videos_generated_this_month || 0) / limit) * 100)
        : 0

    const tierColors: Record<string, string> = {
        free: "text-slate-500",
        pro: "text-indigo-500",
        enterprise: "text-orange-500",
    }

    return (
        <div className="space-y-8 max-w-5xl mx-auto py-6">
            <div className="flex flex-col gap-2">
                <h2 className="text-4xl font-extrabold tracking-tight">Billing & Plans</h2>
                <p className="text-muted-foreground text-sm">Manage your monthly generation quota and Lemon Squeezy subscription.</p>
            </div>

            {/* Current Plan & Usage Bento */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4 border-border/40 shadow-sm bg-gradient-to-br from-background to-muted/20">
                    <CardHeader>
                        <CardTitle className="text-lg">Generation Quota</CardTitle>
                        <CardDescription>
                            {usage?.videos_generated_this_month || 0} of {limitDisplay} videos produced this cycle.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="px-6 pb-6 pt-2">
                        {!isUnlimited ? (
                            <div className="space-y-3">
                                <div className="h-3.5 w-full bg-muted/60 rounded-full overflow-hidden shadow-inner flex">
                                    <div
                                        className="h-full bg-primary transition-all duration-700 ease-out"
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                                <div className="flex justify-between items-center text-xs text-muted-foreground font-medium">
                                    <span>{progress.toFixed(0)}% Used</span>
                                    <span>{limit - (usage?.videos_generated_this_month || 0)} Remaining</span>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 text-emerald-500 font-semibold bg-emerald-500/10 w-fit px-4 py-2 rounded-lg">
                                <Zap className="h-5 w-5" />
                                <span>Unlimited Bandwidth Unlocked</span>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="col-span-3 border-border/40 shadow-sm">
                    <CardHeader>
                        <CardDescription className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">Active Plan</CardDescription>
                        <CardTitle className="flex items-center gap-2 text-2xl">
                            <Crown className={`h-6 w-6 ${tierColors[currentTier] || ""}`} />
                            {currentTier.toUpperCase()}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <div className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                            Status: <span className={`font-bold px-2 py-0.5 rounded text-xs ${isActive ? 'bg-emerald-500/10 text-emerald-500' : 'bg-slate-500/10 text-slate-500'}`}>
                                {isActive ? "PREMIUM" : "BASIC TIER"}
                            </span>
                        </div>
                        {subStatus?.ends_at && (
                            <p className="text-xs text-muted-foreground mt-3">Renews securely on: {new Date(subStatus.ends_at).toLocaleDateString()}</p>
                        )}
                    </CardContent>
                    <CardFooter>
                        {currentTier !== "free" ? (
                            <Button className="w-full font-semibold border-primary/20 hover:bg-muted" variant="outline" onClick={handleManageSubscription} disabled={actionLoading}>
                                <CreditCard className="mr-2 h-4 w-4" /> Customer Portal
                            </Button>
                        ) : (
                            <div className="p-3 bg-muted/30 rounded-lg w-full text-center text-xs text-muted-foreground">
                                Upgrade to Pro to bypass limitations.
                            </div>
                        )}
                    </CardFooter>
                </Card>
            </div>

            {/* Pricing Section */}
            <div className="mt-8">
                <h3 className="text-xl font-bold mb-4 flex items-center gap-2">Available Tiers</h3>
                <div className="grid gap-6 md:grid-cols-3">

                    {/* FREE */}
                    <Card className={`relative overflow-hidden transition-all duration-300 ${currentTier === "free" ? "border-primary/50 shadow-md ring-1 ring-primary/20 scale-[1.02]" : "border-border/40 opacity-90 shadow-sm"}`}>
                        {currentTier === "free" && <div className="absolute top-0 right-0 left-0 h-1 bg-slate-500" />}
                        <CardHeader>
                            <CardTitle>Free</CardTitle>
                            <CardDescription>Exploration mode</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="text-4xl font-extrabold tracking-tight">$0<span className="text-lg font-medium text-muted-foreground">/mo</span></p>
                            <ul className="mt-6 space-y-3 text-sm text-muted-foreground font-medium">
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-emerald-500 shrink-0" /> 3 Videos / Month</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-emerald-500 shrink-0" /> Standard Generation Speed</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-emerald-500 shrink-0" /> Manual Background Downloads</li>
                            </ul>
                        </CardContent>
                        <CardFooter className="pt-4">
                            <Button className="w-full font-semibold bg-muted hover:bg-muted text-muted-foreground" disabled>
                                {currentTier === "free" ? "Active Plan" : "Downgrade Contact Support"}
                            </Button>
                        </CardFooter>
                    </Card>

                    {/* PRO */}
                    <Card className={`relative overflow-hidden transition-all duration-300 ${currentTier === "pro" ? "border-indigo-500 shadow-xl ring-2 ring-indigo-500/50 scale-[1.05] z-10" : "border-border/40 shadow-md hover:border-primary/30"}`}>
                        <div className="absolute top-0 right-0 left-0 h-1 bg-indigo-500" />
                        <CardHeader pb-0>
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-indigo-500">Pro</CardTitle>
                                {currentTier !== "pro" && <span className="bg-indigo-500/10 text-indigo-500 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">Most Popular</span>}
                            </div>
                            <CardDescription>For serious creators</CardDescription>
                        </CardHeader>
                        <CardContent className="mt-2">
                            <p className="text-4xl font-extrabold tracking-tight">$29<span className="text-lg font-medium text-muted-foreground">/mo</span></p>
                            <ul className="mt-6 space-y-3 text-sm font-medium">
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-indigo-500 shrink-0" /> 30 Videos / Month</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-indigo-500 shrink-0" /> Enhanced Parallel Processing ⚡</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-indigo-500 shrink-0" /> Premium Voice Allocation</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-indigo-500 shrink-0" /> Priority Support</li>
                            </ul>
                        </CardContent>
                        <CardFooter className="pt-4">
                            {currentTier === "pro" ? (
                                <Button className="w-full font-semibold bg-indigo-500/10 text-indigo-500 hover:bg-indigo-500/20" variant="secondary">Manage Subscription</Button>
                            ) : (
                                <Button className="w-full font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-md transition-all group" onClick={() => handleUpgrade("pro")} disabled={actionLoading}>
                                    Upgrade to Pro <ArrowRight className="ml-2 h-4 w-4 opacity-70 group-hover:translate-x-1 transition-transform" />
                                </Button>
                            )}
                        </CardFooter>
                    </Card>

                    {/* ENTERPRISE */}
                    <Card className={`relative overflow-hidden transition-all duration-300 ${currentTier === "enterprise" ? "border-orange-500 shadow-lg ring-1 ring-orange-500/50 scale-[1.02]" : "border-border/40 opacity-90 shadow-sm hover:border-primary/30"}`}>
                        {currentTier === "enterprise" && <div className="absolute top-0 right-0 left-0 h-1 bg-orange-500" />}
                        <CardHeader>
                            <CardTitle className="text-orange-500">Enterprise</CardTitle>
                            <CardDescription>For agencies & scale</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="text-4xl font-extrabold tracking-tight">$99<span className="text-lg font-medium text-muted-foreground">/mo</span></p>
                            <ul className="mt-6 space-y-3 text-sm font-medium">
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-orange-500 shrink-0" /> Unlimited Video Generations</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-orange-500 shrink-0" /> White-label Architecture</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-orange-500 shrink-0" /> Dedicated Cloud Instance</li>
                                <li className="flex items-start"><Check className="mr-3 h-5 w-5 text-orange-500 shrink-0" /> Direct API Access</li>
                            </ul>
                        </CardContent>
                        <CardFooter className="pt-4">
                            {currentTier === "enterprise" ? (
                                <Button className="w-full font-semibold bg-orange-500/10 text-orange-500 hover:bg-orange-500/20" variant="secondary">Manage Subscription</Button>
                            ) : (
                                <Button className="w-full font-semibold hover:bg-orange-600 hover:text-white transition-colors" variant="outline" onClick={() => handleUpgrade("enterprise")} disabled={actionLoading}>
                                    Upgrade to Enterprise
                                </Button>
                            )}
                        </CardFooter>
                    </Card>

                </div>
            </div>

            <div className="pt-8 w-full border-t border-border/40 mt-12 flex justify-center pb-8">
                <p className="text-xs text-muted-foreground flex items-center gap-1">Secure payments powered by <span className="font-bold text-yellow-500 flex items-center mx-1">🍋 Lemon Squeezy</span></p>
            </div>
        </div>
    )
}
