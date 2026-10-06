"use client";

import { ReactNode, useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

type RevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
};

export function Reveal({ children, className = "", delay = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!ref.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const context = gsap.context(() => {
      gsap.fromTo(
        ref.current,
        { autoAlpha: 0, y: 18 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.68,
          delay,
          ease: "power3.out",
          clearProps: "transform",
          scrollTrigger: { trigger: ref.current, start: "top 88%", once: true },
        },
      );
    }, ref);

    return () => context.revert();
  }, [delay]);

  return <div ref={ref} className={className}>{children}</div>;
}

type TextRevealProps = RevealProps & {
  as?: "div" | "h1" | "h2" | "h3" | "p" | "span";
};

export function TextReveal({ children, className = "", delay = 0, as = "div" }: TextRevealProps) {
  const ref = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    if (!ref.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const context = gsap.context(() => {
      gsap.fromTo(
        ref.current,
        { autoAlpha: 0, y: 20, clipPath: "inset(0 0 100% 0)" },
        {
          autoAlpha: 1,
          y: 0,
          clipPath: "inset(0 0 0% 0)",
          duration: 0.82,
          delay,
          ease: "power3.out",
          clearProps: "transform,clipPath",
        },
      );
    }, ref);

    return () => context.revert();
  }, [delay]);

  return (
    <>
      {(() => {
        const Tag = as;
        return <Tag ref={(node) => { ref.current = node; }} className={className}>{children}</Tag>;
      })()}
    </>
  );
}

type WordRevealProps = {
  text: string;
  className?: string;
  delay?: number;
  as?: "h1" | "h2" | "h3" | "p" | "span" | "div";
};

export function WordReveal({ text, className = "", delay = 0, as = "h1" }: WordRevealProps) {
  const containerRef = useRef<HTMLElement | null>(null);
  const words = text.split(" ");

  useLayoutEffect(() => {
    if (!containerRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const context = gsap.context(() => {
      const wordSpans = containerRef.current?.querySelectorAll(".word-reveal-token");
      if (!wordSpans?.length) return;

      gsap.fromTo(
        wordSpans,
        { autoAlpha: 0, y: 16, filter: "blur(5px)" },
        {
          autoAlpha: 1,
          y: 0,
          filter: "blur(0px)",
          duration: 0.72,
          delay,
          stagger: 0.045,
          ease: "power2.out",
          clearProps: "transform,filter",
        },
      );
    }, containerRef);

    return () => context.revert();
  }, [delay]);

  const Tag = as;
  return (
    <Tag ref={(node) => { containerRef.current = node; }} className={`word-reveal-container ${className}`}>
      {words.map((word, i) => (
        <span key={`${word}-${i}`} className="word-reveal-token" style={{ display: "inline-block", marginRight: "0.28em" }}>
          {word}
        </span>
      ))}
    </Tag>
  );
}

export function GentleFade({ children, className = "", delay = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!ref.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const context = gsap.context(() => {
      gsap.fromTo(
        ref.current,
        { autoAlpha: 0, scale: 0.98 },
        {
          autoAlpha: 1,
          scale: 1,
          duration: 0.85,
          delay,
          ease: "power2.out",
          clearProps: "transform",
        },
      );
    }, ref);

    return () => context.revert();
  }, [delay]);

  return <div ref={ref} className={className}>{children}</div>;
}

