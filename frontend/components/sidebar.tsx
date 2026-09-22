"use client";

import {
  BarChart3,
  BriefcaseBusiness,
  ChevronLeft,
  ClipboardCheck,
  FileSearch,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge, Button } from "@/components/ui";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Overview", icon: LayoutDashboard, href: "/overview" },
  { name: "Candidate Screening", icon: FileSearch, href: "/screening" },
  { name: "Candidates", icon: Users, href: "/screening", pending: false },
  { name: "Jobs", icon: BriefcaseBusiness, href: "/jobs" },
  { name: "Online Assessment", icon: ClipboardCheck, href: "#", pending: true },
  { name: "Analytics", icon: BarChart3, href: "#", pending: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="secondary" size="icon" className="fixed left-4 top-4 z-40 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
        <Menu className="size-5" />
      </Button>
      {open && <button className="fixed inset-0 z-40 bg-black/30 lg:hidden" aria-label="Close navigation overlay" onClick={() => setOpen(false)} />}
      <aside className={cn("fixed inset-y-0 left-0 z-50 flex w-[220px] flex-col border-r bg-white transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex h-[68px] items-center justify-between border-b px-4">
          <Link href="/screening" className="flex items-center gap-3">
            <BrandMark />
            <span><span className="block text-base font-bold leading-none text-[#22233a]">Catalyst AI</span><span className="mt-1 block text-[9px] font-semibold uppercase tracking-[.16em] text-[#9897a7]">Talent Intelligence</span></span>
          </Link>
          <button className="text-[#98a2b3] lg:hidden" onClick={() => setOpen(false)} aria-label="Close navigation"><X className="size-5" /></button>
        </div>
        <nav className="flex-1 space-y-1 px-2 py-5">
          <p className="mb-3 px-3 text-[11px] font-bold uppercase tracking-wider text-[#98a2b3]">Workspace</p>
          {navigation.map((item) => {
            const active = item.href !== "#" && pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={(event) => {
                  if (item.pending) event.preventDefault();
                  else setOpen(false);
                }}
                className={cn("relative flex h-10 items-center gap-3 rounded-md px-3 text-[13px] font-medium transition", active ? "bg-[#fff0f7] font-semibold text-[#c0086d] before:absolute before:-left-2 before:h-6 before:w-[3px] before:rounded-r before:bg-primary" : "text-[#606174] hover:bg-muted hover:text-[#2c2d42]")}
              >
                <item.icon className="size-[18px]" />
                <span className="flex-1">{item.name}</span>
                {item.pending && <Badge className="px-1.5 text-[9px]">Soon</Badge>}
              </Link>
            );
          })}
        </nav>
        <div className="border-t p-3">
          <a href="#" onClick={(event) => event.preventDefault()} className="flex h-10 items-center gap-3 rounded-lg px-3 text-sm text-[#667085] hover:bg-muted"><Settings className="size-[18px]" />Settings<Badge className="ml-auto px-1.5 text-[9px]">Soon</Badge></a>
          <div className="mt-3 flex items-center gap-3 rounded-lg bg-[#faf9fb] p-3">
            <span className="flex size-9 items-center justify-center rounded-full bg-[#ffd9eb] text-xs font-bold text-[#b00665]">AR</span>
            <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">Recruiting Team</span><span className="block truncate text-xs text-[#98a2b3]">Talent workspace</span></span>
            <button title="Sign out unavailable" className="text-[#98a2b3]"><LogOut className="size-4" /></button>
          </div>
        </div>
      </aside>
      <div className="fixed bottom-5 left-[204px] z-50 hidden size-8 items-center justify-center rounded-full border bg-white text-[#98a2b3] shadow-sm lg:flex"><ChevronLeft className="size-4" /></div>
    </>
  );
}

function BrandMark() {
  return (
    <span className="relative block h-7 w-10 shrink-0" aria-hidden="true">
      <span className="absolute left-0 top-2 size-3 rotate-45 rounded-[2px] bg-[#e5007d]" />
      <span className="absolute left-3 top-2 size-3 rotate-45 rounded-[2px] bg-[#b20a7c]" />
      <span className="absolute left-6 top-2 size-3 rotate-45 rounded-[2px] bg-[#3152a4]" />
    </span>
  );
}
