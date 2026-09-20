"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { X } from "lucide-react";
import React from "react";
import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "primary",
  size = "default",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "default" | "icon" | "sm";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md text-sm font-semibold transition duration-200 disabled:pointer-events-none disabled:opacity-50",
        variant === "primary" && "bg-primary text-white shadow-sm shadow-primary/20 hover:bg-[#b70769]",
        variant === "secondary" && "border bg-white text-[#34354a] hover:border-[#e2a0c4] hover:bg-[#fff7fb]",
        variant === "ghost" && "text-[#6f7082] hover:bg-[#fff0f7] hover:text-primary",
        variant === "danger" && "bg-red-50 text-red-700 hover:bg-red-100",
        size === "default" && "h-10 px-4",
        size === "sm" && "h-8 px-3 text-xs",
        size === "icon" && "size-9 p-0",
        className,
      )}
      {...props}
    />
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "h-10 w-full rounded-md border bg-white px-3 text-sm text-[#34354a] shadow-sm placeholder:text-[#9b9bab] focus:border-primary focus:ring-2 focus:ring-[#ffd4e9]",
          className,
        )}
        {...props}
      />
    );
  },
);

export function Badge({
  children,
  tone = "gray",
  className,
}: {
  children: React.ReactNode;
  tone?: "gray" | "purple" | "green" | "amber" | "red";
  className?: string;
}) {
  const tones = {
    gray: "bg-[#f2f4f7] text-[#667085]",
    purple: "bg-[#fff0f7] text-[#b00665]",
    green: "bg-[#ecfdf3] text-[#027a48]",
    amber: "bg-[#fffaeb] text-[#b54708]",
    red: "bg-[#fef3f2] text-[#b42318]",
  };
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-semibold", tones[tone], className)}>{children}</span>;
}

export function Progress({ value }: { value: number }) {
  return (
    <ProgressPrimitive.Root className="relative h-2 overflow-hidden rounded-full bg-[#eaecf0]" value={value}>
      <ProgressPrimitive.Indicator
        className="h-full bg-primary transition-transform duration-500"
        style={{ transform: `translateX(-${100 - value}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  children,
  className,
  title,
  description,
}: {
  children: React.ReactNode;
  className?: string;
  title: string;
  description?: string;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#101828]/40 backdrop-blur-[2px]" />
      <DialogPrimitive.Content className={cn("fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border bg-white p-6 shadow-2xl", className)}>
        <DialogPrimitive.Title className="text-lg font-semibold text-[#101828]">{title}</DialogPrimitive.Title>
        {description && <DialogPrimitive.Description className="mt-1 text-sm text-[#667085]">{description}</DialogPrimitive.Description>}
        {children}
        <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md p-1 text-[#98a2b3] hover:bg-muted" aria-label="Close">
          <X className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("relative overflow-hidden rounded bg-[#eef0f3] before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_1.5s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/70 before:to-transparent", className)} />;
}
