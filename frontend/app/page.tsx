import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Play, Sparkles, Youtube, Zap } from "lucide-react"

export default function Home() {
  return (
    <main className="min-h-screen bg-[#050510] relative overflow-hidden text-slate-100 flex flex-col justify-center pb-20 md:pb-32">
      {/* Decorative background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-600/20 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-6xl mx-auto px-6 relative z-10 w-full">
        {/* Header */}
        <header className="absolute top-0 left-0 right-0 p-6 flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
            <Youtube className="h-7 w-7 text-red-600" />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-red-500 to-red-600">AutoTube</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm font-medium hover:text-white transition-colors text-slate-300">
              Sign In
            </Link>
            <Link href="/register">
              <Button className="bg-white text-black hover:bg-slate-200 rounded-full px-6 shadow-xl">
                Start Free
              </Button>
            </Link>
          </div>
        </header>

        {/* Hero Section */}
        <div className="pt-24 pb-20 md:pt-32 md:pb-28 text-center max-w-4xl mx-auto space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-300 shadow-sm backdrop-blur-md mb-4">
            <Sparkles className="h-3.5 w-3.5 text-red-500" />
            <span>v2.0 Autonomous Engine Live</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.1] text-balance">
            Deploy your own <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-500 via-orange-500 to-red-500 animate-gradient-x">
              Viral Media Empire
            </span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed text-balance">
            Connect your YouTube channel and let our advanced AI autonomously research trends, write scripts, render videos, and publish your content entirely on autopilot.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-6">
            <Link href="/register">
              <Button size="lg" className="h-14 px-8 text-base bg-red-600 hover:bg-red-700 text-white rounded-full shadow-[0_0_40px_-10px_rgba(220,38,38,0.5)] transition-all hover:scale-105 group">
                <Play className="mr-2 h-4 w-4 fill-white group-hover:animate-pulse" />
                Initialize Deployment
              </Button>
            </Link>
          </div>
        </div>

        {/* Features minimal grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-12 mt-8 md:mt-12 border-t border-white/5 mx-auto max-w-5xl text-left relative z-10">
          <div className="group p-6 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/5 hover:border-red-500/30 backdrop-blur-sm transition-all duration-300 hover:-translate-y-2 cursor-pointer shadow-lg hover:shadow-red-500/10">
            <div className="h-10 w-10 bg-red-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-red-500/20 group-hover:scale-110 transition-all duration-300">
              <Zap className="h-5 w-5 text-red-500 group-hover:drop-shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
            </div>
            <h3 className="font-semibold text-white mb-2 group-hover:text-red-400 transition-colors">100% Autopilot Mode</h3>
            <p className="text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">Simply define your niche. Our AI researches trends, writes scripts, and auto-publishes optimized Shorts daily—no humans required.</p>
          </div>
          <div className="group p-6 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/5 hover:border-purple-500/30 backdrop-blur-sm transition-all duration-300 hover:-translate-y-2 cursor-pointer shadow-lg hover:shadow-purple-500/10">
            <div className="h-10 w-10 bg-purple-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-purple-500/20 group-hover:scale-110 transition-all duration-300">
              <Sparkles className="h-5 w-5 text-purple-500 group-hover:drop-shadow-[0_0_8px_rgba(168,85,247,0.8)]" />
            </div>
            <h3 className="font-semibold text-white mb-2 group-hover:text-purple-400 transition-colors">Hollywood-Grade Renders</h3>
            <p className="text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">Captivate your audience with high-retention visuals, hyper-realistic voiceovers, and pulse-pounding dynamic karaoke subtitles.</p>
          </div>
          <div className="group p-6 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/5 hover:border-green-500/30 backdrop-blur-sm transition-all duration-300 hover:-translate-y-2 cursor-pointer shadow-lg hover:shadow-green-500/10">
            <div className="h-10 w-10 bg-green-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-green-500/20 group-hover:scale-110 transition-all duration-300">
              <svg className="h-5 w-5 text-green-500 group-hover:drop-shadow-[0_0_8px_rgba(34,197,94,0.8)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
            </div>
            <h3 className="font-semibold text-white mb-2 group-hover:text-green-400 transition-colors">Algorithmic Dominance</h3>
            <p className="text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">Stop guessing what goes viral. We scrape real-time Reddit discussions and Google Trends to guarantee maximum algorithmic reach.</p>
          </div>
        </div>
      </div>
    </main>
  )
}
