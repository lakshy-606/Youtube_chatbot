import type { Metadata } from "next";
import { AboutContent } from "@/components/AboutContent";

export const metadata: Metadata = {
  title: "About — YouTube RAG Chatbot",
  description: "How this RAG chatbot is built, component by component.",
};

export default function AboutPage() {
  return <AboutContent />;
}
